package com.humanaize.aizecompanion.service

import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.wifi.WifiManager
import android.os.IBinder
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.net.InetAddress
import java.net.NetworkInterface

/**
 * 设备发现服务
 * 
 * 扫描局域网内的 Humanaize 2.0 服务端，
 * 方便用户快速发现和连接。
 */
class DiscoveryService : Service() {
    
    companion object {
        private const val TAG = "DiscoveryService"
        private const val DEFAULT_PORT = 8765
        private const val DISCOVERY_TIMEOUT = 3000 // 3秒
        private const val SCAN_INTERVAL = 10000 // 10秒
        
        private const val ACTION_DISCOVER = "com.humanaize.aizecompanion.DISCOVER"
        private const val EXTRA_SERVERS = "discovered_servers"
        
        fun start(context: Context) {
            val intent = Intent(context, DiscoveryService::class.java).apply {
                action = ACTION_DISCOVER
            }
            context.startService(intent)
        }
    }
    
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var scanJob: Job? = null
    
    override fun onBind(intent: Intent?): IBinder? = null
    
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_DISCOVER) {
            startDiscovery()
        }
        return START_STICKY
    }
    
    override fun onDestroy() {
        scanJob?.cancel()
        scope.cancel()
        super.onDestroy()
    }
    
    private fun startDiscovery() {
        scanJob?.cancel()
        scanJob = scope.launch {
            while (isActive) {
                discoverServers()
                delay(SCAN_INTERVAL.toLong())
            }
        }
    }
    
    private suspend fun discoverServers() {
        try {
            val localIp = getLocalIpAddress()
            if (localIp == null) {
                Log.w(TAG, "Cannot get local IP address")
                return
            }
            
            Log.i(TAG, "Starting discovery from $localIp")
            
            val subnet = localIp.substringBeforeLast('.')
            val discoveredServers = mutableListOf<String>()
            
            // 扫描局域网 1-254
            for (i in 1..254) {
                val ip = "$subnet.$i"
                try {
                    val address = InetAddress.getByName(ip)
                    if (address.isReachable(DISCOVERY_TIMEOUT)) {
                        // 尝试连接 WebSocket 端口
                        if (checkPortOpen(ip, DEFAULT_PORT)) {
                            discoveredServers.add("ws://$ip:$DEFAULT_PORT")
                            Log.i(TAG, "Discovered server at ws://$ip:$DEFAULT_PORT")
                        }
                    }
                } catch (e: Exception) {
                    // 忽略不可达的 IP
                }
                
                // 每次扫描间隔
                delay(50)
            }
            
            // 发送结果
            if (discoveredServers.isNotEmpty()) {
                sendDiscoveryResults(discoveredServers)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Discovery error: ${e.message}")
        }
    }
    
    private fun getLocalIpAddress(): String? {
        try {
            val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            val wifiInfo = wifiManager.connectionInfo
            val intIp = wifiInfo.ipAddress
            return String.format(
                "%d.%d.%d.%d",
                intIp and 0xFF,
                intIp shr 8 and 0xFF,
                intIp shr 16 and 0xFF,
                intIp shr 24 and 0xFF
            )
        } catch (e: Exception) {
            // 回退方案
            try {
                val networkInterfaces = NetworkInterface.getNetworkInterfaces()
                networkInterfaces?.toList()?.forEach { networkInterface ->
                    val addrs = networkInterface.inetAddresses
                    addrs?.toList()?.forEach { addr ->
                        if (!addr.isLoopbackAddress && addr is java.net.Inet4Address) {
                            return addr.hostAddress
                        }
                    }
                }
            } catch (e2: Exception) {
                Log.e(TAG, "Cannot get local IP: ${e2.message}")
            }
        }
        return null
    }
    
    private fun checkPortOpen(ip: String, port: Int): Boolean {
        return try {
            val socket = java.net.Socket()
            socket.connect(java.net.InetSocketAddress(ip, port), 2000)
            socket.close()
            true
        } catch (e: Exception) {
            false
        }
    }
    
    private fun sendDiscoveryResults(servers: List<String>) {
        // 通过广播或回调通知结果
        // 这里简化处理，使用本地广播
        val intent = Intent(EXTRA_SERVERS).apply {
            putStringArrayListExtra("servers", ArrayList(servers))
            setPackage(packageName)
        }
        sendBroadcast(intent)
    }
}
