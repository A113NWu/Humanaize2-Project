package com.humanaize.aizecompanion.network

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import okhttp3.Call
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * PC 端 Humanaize2 後端 API 客戶端
 *
 * - 登錄：POST /api/login，從 Set-Cookie 提取 humanaize_session，
 *   之後統一用 Authorization: Bearer <token>（後端兩種都認）
 * - 聊天：POST /api/chat（SSE 流式，OpenAI chunk 格式，
 *   thought=true 的幀是思考/技能日誌，不是回覆正文）
 * - 手機命令：GET /api/phone/poll?since=N 取命令，POST /api/phone/result 回傳
 */
class AizeApiClient(
    private var baseUrl: String,
    private var token: String
) {

    companion object {
        private const val TAG = "AizeApi"
        private val JSON_MEDIA = "application/json; charset=utf-8".toMediaType()
    }

    private val json = Json { ignoreUnknownKeys = true }

    // SSE 需要長連接：read timeout 放寬
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    fun updateConfig(baseUrl: String, token: String) {
        this.baseUrl = baseUrl.trimEnd('/')
        this.token = token
    }

    val configured: Boolean get() = baseUrl.isNotEmpty()

    private fun Request.Builder.withAuth(): Request.Builder {
        if (token.isNotEmpty()) header("Authorization", "Bearer $token")
        return this
    }

    /** 健康檢查（免登錄），用於測試服務器連通性 */
    suspend fun health(): Result<Boolean> = withContext(Dispatchers.IO) {
        runCatching {
            if (!configured) return@runCatching false
            val req = Request.Builder().url("$baseUrl/health").build()
            client.newCall(req).execute().use { it.isSuccessful }
        }
    }

    /**
     * 登錄：成功返回 session token；後端未開賬號認證時返回空串（表示免登錄）
     */
    suspend fun login(username: String, password: String): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            check(configured) { "請先填寫服務器地址" }
            val body = """{"username":${json.encodeToString(username)},""" +
                    """"password":${json.encodeToString(password)}}"""
            val req = Request.Builder()
                .url("$baseUrl/api/login")
                .post(body.toRequestBody(JSON_MEDIA))
                .build()
            client.newCall(req).execute().use { resp ->
                val text = resp.body?.string().orEmpty()
                if (resp.code == 401) throw Exception("賬號或密碼錯誤")
                if (!resp.isSuccessful) throw Exception("登錄失敗 HTTP ${resp.code}: $text")
                val obj = runCatching { json.parseToJsonElement(text).jsonObject }.getOrNull()
                if (obj?.get("auth_required")?.jsonPrimitive?.boolean == false) {
                    return@runCatching "" // 免登錄模式
                }
                val cookie = resp.headers("Set-Cookie").firstOrNull { it.startsWith("humanaize_session=") }
                    ?: throw Exception("未收到會話憑證")
                cookie.substringAfter("humanaize_session=").substringBefore(";")
            }
        }
    }

    // ---------- 聊天（SSE 流式） ----------

    sealed class ChatEvent {
        data class Text(val content: String) : ChatEvent()

        /** 思考/技能日誌幀（不混入正文）；kind: thought 類型或 skill */
        data class Log(val kind: String, val content: String) : ChatEvent()

        data class Error(val message: String) : ChatEvent()

        /** 服務器 409：上一輪還在生成（客戶端已斷線但後端未釋放） */
        object Busy : ChatEvent()

        object Done : ChatEvent()
    }

    /** 当前正在进行的流式请求；打断/发新消息时取消它，后端的 BrokenPipe 分支会同步取消生成 */
    @Volatile
    private var activeChatCall: Call? = null

    fun cancelActiveChat() {
        activeChatCall?.cancel()
        activeChatCall = null
    }

    /**
     * 讓 PC 端子 Agent 判斷「新消息是否要打斷當前回覆」。
     * 返回 interrupt=false 表示繼續講完當前回覆，新消息排隊等當前結束再發。
     */
    data class InterruptVerdict(val interrupt: Boolean, val idle: Boolean, val reason: String)

    suspend fun requestInterrupt(text: String): Result<InterruptVerdict> = withContext(Dispatchers.IO) {
        runCatching {
            check(configured) { "未配置服務器" }
            val body = """{"text":${json.encodeToString(text)}}"""
            val req = Request.Builder()
                .url("$baseUrl/api/chat/interrupt")
                .withAuth()
                .post(body.toRequestBody(JSON_MEDIA))
                .build()
            val shortClient = client.newBuilder().readTimeout(30, TimeUnit.SECONDS).build()
            shortClient.newCall(req).execute().use { resp ->
                if (resp.code == 401) throw SessionExpiredException()
                if (!resp.isSuccessful) throw Exception("HTTP ${resp.code}")
                val o = json.parseToJsonElement(resp.body!!.string()).jsonObject
                InterruptVerdict(
                    interrupt = o["interrupt"]?.jsonPrimitive?.boolean ?: true,
                    idle = o["idle"]?.jsonPrimitive?.boolean ?: false,
                    reason = o["reason"]?.jsonPrimitive?.contentOrNull ?: ""
                )
            }
        }
    }

    fun chatStream(message: String): Flow<ChatEvent> = flow {
        check(configured) { "請先在設定頁填寫服務器地址" }
        val escaped = json.encodeToString(message)
        val body = """{"messages":[{"role":"user","content":$escaped}],"stream":true}"""
        val req = Request.Builder()
            .url("$baseUrl/api/chat")
            .withAuth()
            .post(body.toRequestBody(JSON_MEDIA))
            .build()

        val call = client.newCall(req)
        activeChatCall = call
        try {
            call.execute().use { resp ->
                if (resp.code == 401) {
                    emit(ChatEvent.Error("未登錄或會話已過期，請到設定頁重新登錄"))
                    return@use
                }
                if (resp.code == 409) {
                    emit(ChatEvent.Busy)
                    return@use
                }
                if (!resp.isSuccessful) {
                    emit(ChatEvent.Error("HTTP ${resp.code}: ${resp.body?.string()?.take(200)}"))
                    return@use
                }
                val source = resp.body?.source() ?: run {
                    emit(ChatEvent.Error("空響應")); return@use
                }
                while (true) {
                    val line = source.readUtf8Line() ?: break
                    if (!line.startsWith("data:")) continue
                    val data = line.substring(5).trim()
                    if (data == "[DONE]") break
                    val obj = runCatching { json.parseToJsonElement(data).jsonObject }.getOrNull()
                        ?: continue
                    val content = obj["choices"]?.jsonArray?.firstOrNull()
                        ?.jsonObject?.get("delta")?.jsonObject
                        ?.get("content")?.jsonPrimitive?.contentOrNull ?: continue
                    if (obj["thought"]?.jsonPrimitive?.boolean == true) {
                        val kind = obj["thought_type"]?.jsonPrimitive?.contentOrNull ?: "thought"
                        emit(ChatEvent.Log(kind, content))
                    } else {
                        emit(ChatEvent.Text(content))
                    }
                }
            }
        } finally {
            if (activeChatCall === call) activeChatCall = null
        }
        emit(ChatEvent.Done)
    }.flowOn(Dispatchers.IO)

    // ---------- 歷史時間線 / 主動消息事件 ----------

    /** 服務器端持久化的對話輪次（重開 App 後用它恢復歷史） */
    data class HistoryTurn(
        val id: String,
        val user: String,
        val text: String,
        val thoughts: String,
        val ts: Long,
        val pending: Boolean
    )

    suspend fun fetchTimeline(): Result<List<HistoryTurn>> = withContext(Dispatchers.IO) {
        runCatching {
            check(configured) { "未配置服務器" }
            val req = Request.Builder().url("$baseUrl/api/chat/timeline").withAuth().build()
            val shortClient = client.newBuilder().readTimeout(20, TimeUnit.SECONDS).build()
            shortClient.newCall(req).execute().use { resp ->
                if (resp.code == 401) throw SessionExpiredException()
                if (!resp.isSuccessful) throw Exception("HTTP ${resp.code}")
                val obj = json.parseToJsonElement(resp.body!!.string()).jsonObject
                obj["turns"]?.jsonArray.orEmpty().mapNotNull { el ->
                    val o = el as? JsonObject ?: return@mapNotNull null
                    val items = o["items"]?.jsonArray.orEmpty()
                    val thoughts = items.filter {
                        (it.jsonObject["k"]?.jsonPrimitive?.contentOrNull ?: "") in
                                setOf("thought", "cmd_start", "cmd_result")
                    }.joinToString("\n") { it.jsonObject["c"]?.jsonPrimitive?.contentOrNull ?: "" }
                    val ts = o["ts"]?.jsonPrimitive?.longOrNull ?: 0L
                    val id = o["id"]?.jsonPrimitive?.contentOrNull ?: "t$ts"
                    val user = o["display_user"]?.jsonPrimitive?.contentOrNull
                        ?: o["user"]?.jsonPrimitive?.contentOrNull ?: ""
                    val allText = items.filter {
                        it.jsonObject["k"]?.jsonPrimitive?.contentOrNull == "text"
                    }.joinToString("") { it.jsonObject["c"]?.jsonPrimitive?.contentOrNull ?: "" }
                    HistoryTurn(
                        id = id,
                        user = user,
                        text = allText,
                        thoughts = thoughts,
                        ts = ts,
                        pending = o["pending"]?.jsonPrimitive?.boolean == true
                    )
                }
            }
        }
    }

    /** Aize 主動推送的有意義事件（autonomous = 主動找主人說話） */
    data class EngineEvent(val type: String, val content: String)

    fun eventStream(): Flow<EngineEvent> = flow {
        check(configured) { "未配置服務器" }
        val req = Request.Builder().url("$baseUrl/api/events").withAuth().build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) return@use
            val source = resp.body?.source() ?: return@use
            while (true) {
                val line = source.readUtf8Line() ?: break
                if (!line.startsWith("data:")) continue
                val data = line.substring(5).trim()
                if (!data.startsWith("{")) continue
                val o = runCatching { json.parseToJsonElement(data).jsonObject }.getOrNull() ?: continue
                val type = o["type"]?.jsonPrimitive?.contentOrNull ?: continue
                val content = o["content"]?.jsonPrimitive?.contentOrNull.orEmpty()
                if (content.isBlank()) continue
                emit(EngineEvent(type, content))
            }
        }
    }.flowOn(Dispatchers.IO)

    // ---------- 手機命令通道 ----------

    data class PhoneCommand(
        val id: Long,
        val command: String,
        val timeoutSec: Int,
        val workDir: String?
    )

    /** 輪詢待執行命令；返回 null 表示請求失敗（保持上次的 since 重試） */
    suspend fun pollPhoneCommands(since: Long, deviceName: String): Result<Pair<List<PhoneCommand>, Boolean>> =
        withContext(Dispatchers.IO) {
            runCatching {
                check(configured) { "未配置服務器" }
                val url = "$baseUrl/api/phone/poll?since=$since&device=${
                    java.net.URLEncoder.encode(deviceName, "UTF-8")}"
                val req = Request.Builder().url(url).withAuth().build()
                // 輪詢用短超時，別被上面的 0 readTimeout 卡住
                val shortClient = client.newBuilder().readTimeout(15, TimeUnit.SECONDS).build()
                shortClient.newCall(req).execute().use { resp ->
                    if (resp.code == 401) throw SessionExpiredException()
                    if (!resp.isSuccessful) throw Exception("HTTP ${resp.code}")
                    val obj = json.parseToJsonElement(resp.body!!.string()).jsonObject
                    val cmds = obj["commands"]?.jsonArray.orEmpty().mapNotNull { el ->
                        val o = el as? JsonObject ?: return@mapNotNull null
                        val id = o["id"]?.jsonPrimitive?.longOrNull ?: return@mapNotNull null
                        val command = o["command"]?.jsonPrimitive?.contentOrNull ?: return@mapNotNull null
                        PhoneCommand(
                            id = id,
                            command = command,
                            timeoutSec = o["timeout"]?.jsonPrimitive?.intOrNull ?: 30,
                            workDir = o["work_dir"]?.jsonPrimitive?.contentOrNull
                        )
                    }
                    val online = obj["status"]?.jsonObject?.get("online")?.jsonPrimitive?.boolean == true
                    cmds to online
                }
            }
        }

    suspend fun postPhoneResult(
        id: Long, success: Boolean, exitCode: Int,
        stdout: String, stderr: String, error: String?, durationMs: Long
    ): Result<Boolean> = withContext(Dispatchers.IO) {
        runCatching {
            check(configured) { "未配置服務器" }
            val resultObj = buildString {
                append("{")
                append("\"success\":$success,")
                append("\"exit_code\":$exitCode,")
                append("\"stdout\":${json.encodeToString(stdout.take(16000))},")
                append("\"stderr\":${json.encodeToString(stderr.take(8000))},")
                append("\"error\":${error?.let { json.encodeToString(it) } ?: "null"},")
                append("\"duration_ms\":$durationMs")
                append("}")
            }
            val body = """{"id":$id,"result":$resultObj}"""
            val req = Request.Builder()
                .url("$baseUrl/api/phone/result")
                .withAuth()
                .post(body.toRequestBody(JSON_MEDIA))
                .build()
            client.newCall(req).execute().use { it.isSuccessful }
        }
    }

    class SessionExpiredException : Exception("會話已過期")

    private fun Json.encodeToString(value: String): String =
        kotlinx.serialization.json.JsonPrimitive(value).toString()
}
