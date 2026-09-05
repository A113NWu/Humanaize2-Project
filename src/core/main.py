"""
Humanaize v2.0 - 主要進入點

命令:
    python main.py boot         - 啟動瀏覽器管理面板
    python main.py boot -m cli  - 啟動 CLI 聊天介面
    python main.py boot -m gui  - 啟動 GUI 介面
    python main.py boot -m win-gui  - 啟動 Windows 現代化 GUI 介面
    python main.py boot -m solve -r <file> -enable HSN - 啟動解決模式
    python main.py boot -m guard [--background] [--start-when-boot] - 啟動守護模式
    python main.py boot -m iot [--host <ip>] [--port <n>] - 啟動 IoT 算力網絡
    python main.py settings     - 開啟設定介面
    python main.py update       - 檢查並安裝更新
"""

import sys
import os
import random
import subprocess
import threading
import json
import time
from typing import Dict

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

try:
    import psycopg2
    import psycopg2.errors
except ImportError:  # pragma: no cover
    psycopg2 = None
    psycopg2_errors = None

# 添加项目根目录和 src 目录到 Python 路径
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(src_dir)
sys.path.insert(0, project_root)
sys.path.insert(0, src_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入并初始化日志模块
from tools.logger import get_logger
logger = get_logger()
logger.redirect_output()
logger.info("Humanaize v2.0 starting...")

import warnings
warnings.filterwarnings("ignore", message=".*iCCP.*known incorrect sRGB profile.*")


def _get_llama_server_path():
    """取得當前平台的正確 llama-server 路徑"""
    if sys.platform != "win32":
        system_paths = [
            "/usr/bin/llama-server",
            "/usr/local/bin/llama-server",
            "/opt/llama.cpp/llama-server"
        ]
        for path in system_paths:
            if os.path.exists(path):
                return path
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    llama_dir = os.path.join(base_dir, "llama")

    if sys.platform == "win32":
        return os.path.join(llama_dir, "llama-server.exe")
    else:
        return os.path.join(llama_dir, "llama-server")


def check_llm_server_status(target_url: str = "http://127.0.0.1:8080/completion", attempts: int = 30, interval: int = 3, timeout: int = 5):
    """Polling test for the local llama completion endpoint. This is the logic previously in check_server.py."""
    if requests is None:
        raise RuntimeError("requests package is required for the server check")

    for i in range(attempts):
        time.sleep(interval)
        try:
            response = requests.post(target_url, json={"prompt": "test", "n_predict": 5}, timeout=timeout)
            print(f"Attempt {i + 1}: Status {response.status_code}")
            if response.status_code == 200:
                print("Server is ready!")
                print(f"Response: {response.text[:200]}")
                return True
        except Exception as exc:  # pragma: no cover - runtime diagnosic function
            print(f"Attempt {i + 1}: {exc}")
    return False


def init_msf_database(host: str = "127.0.0.1", port: int = 5432, database: str = "msf", user: str = "msf", password: str = ""):
    """Initialize the MSF PostgreSQL schema. This consolidates the logic from init_msf_db.py."""
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required to initialize the MSF database")

    db_config = {
        "host": host,
        "port": port,
        "database": database,
        "user": user,
        "password": password,
    }

    create_tables_sql = [
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            boundary VARCHAR(4096),
            description VARCHAR(4096),
            owner_id INTEGER,
            limit_to_network BOOLEAN NOT NULL DEFAULT FALSE,
            import_fingerprint BOOLEAN DEFAULT FALSE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS hosts (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            address INET NOT NULL,
            mac VARCHAR(255),
            comm VARCHAR(255),
            name VARCHAR(255),
            state VARCHAR(255),
            os_name VARCHAR(255),
            os_flavor VARCHAR(255),
            os_sp VARCHAR(255),
            os_lang VARCHAR(255),
            arch VARCHAR(255),
            workspace_id INTEGER NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            purpose TEXT,
            info VARCHAR(65536),
            comments TEXT,
            scope TEXT,
            virtual_host TEXT,
            note_count INTEGER DEFAULT 0,
            vuln_count INTEGER DEFAULT 0,
            service_count INTEGER DEFAULT 0,
            host_detail_count INTEGER DEFAULT 0,
            exploit_attempt_count INTEGER DEFAULT 0,
            cred_count INTEGER DEFAULT 0,
            detected_arch VARCHAR(255),
            os_family VARCHAR(255),
            CONSTRAINT unique_host_address UNIQUE (workspace_id, address)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS services (
            id SERIAL PRIMARY KEY,
            host_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            port INTEGER NOT NULL,
            proto VARCHAR(16) NOT NULL,
            state VARCHAR(255),
            name VARCHAR(255),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            info TEXT,
            resource JSONB NOT NULL DEFAULT '{}'
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS vulns (
            id SERIAL PRIMARY KEY,
            host_id INTEGER,
            service_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            name VARCHAR(255),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            info VARCHAR(65536),
            exploited_at TIMESTAMP,
            vuln_detail_count INTEGER DEFAULT 0,
            vuln_attempt_count INTEGER DEFAULT 0,
            origin_id INTEGER,
            origin_type VARCHAR(255),
            resource JSONB NOT NULL DEFAULT '{}'
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS vuln_details (
            id SERIAL PRIMARY KEY,
            vuln_id INTEGER,
            cvss_score FLOAT,
            cvss_vector VARCHAR(255),
            title VARCHAR(255),
            description TEXT,
            solution TEXT,
            proof BYTEA,
            nx_console_id INTEGER,
            nx_device_id INTEGER,
            nx_vuln_id VARCHAR(255),
            nx_severity FLOAT,
            nx_pci_severity FLOAT,
            nx_published TIMESTAMP,
            nx_added TIMESTAMP,
            nx_modified TIMESTAMP,
            nx_tags TEXT,
            nx_vuln_status TEXT,
            nx_proof_key TEXT,
            src VARCHAR(255),
            nx_scan_id INTEGER,
            nx_vulnerable_since TIMESTAMP,
            nx_pci_compliance_status VARCHAR(255)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS creds (
            id SERIAL PRIMARY KEY,
            service_id INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "user" VARCHAR(2048),
            "pass" VARCHAR(4096),
            active BOOLEAN DEFAULT TRUE,
            proof VARCHAR(4096),
            ptype VARCHAR(256),
            source_id INTEGER,
            source_type VARCHAR(255)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            host_id INTEGER,
            stype VARCHAR(255),
            via_exploit VARCHAR(255),
            via_payload VARCHAR(255),
            "desc" VARCHAR(255),
            port INTEGER,
            platform VARCHAR(255),
            datastore TEXT,
            opened_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            close_reason VARCHAR(255),
            local_id INTEGER,
            last_seen TIMESTAMP,
            module_run_id INTEGER
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ntype VARCHAR(512),
            workspace_id INTEGER NOT NULL DEFAULT 1,
            service_id INTEGER,
            host_id INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            critical BOOLEAN,
            seen BOOLEAN,
            data TEXT,
            vuln_id INTEGER
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS loots (
            id SERIAL PRIMARY KEY,
            workspace_id INTEGER NOT NULL DEFAULT 1,
            host_id INTEGER,
            service_id INTEGER,
            ltype VARCHAR(512),
            path VARCHAR(1024),
            data TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            content_type VARCHAR(255),
            name TEXT,
            info TEXT,
            module_run_id INTEGER
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS exploit_attempts (
            id SERIAL PRIMARY KEY,
            host_id INTEGER,
            service_id INTEGER,
            vuln_id INTEGER,
            attempted_at TIMESTAMP,
            exploited BOOLEAN,
            fail_reason VARCHAR(255),
            username VARCHAR(255),
            module TEXT,
            session_id INTEGER,
            loot_id INTEGER,
            port INTEGER,
            proto VARCHAR(16),
            fail_detail TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS module_details (
            id SERIAL PRIMARY KEY,
            mtime TIMESTAMP,
            file TEXT,
            mtype VARCHAR(255),
            refname TEXT,
            fullname TEXT,
            name TEXT,
            rank INTEGER,
            description TEXT,
            license VARCHAR(255),
            privileged BOOLEAN,
            disclosure_date TIMESTAMP,
            default_target INTEGER,
            default_action TEXT,
            stance VARCHAR(255),
            ready BOOLEAN
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS mod_refs (
            id SERIAL PRIMARY KEY,
            module VARCHAR(1024),
            mtype VARCHAR(128),
            ref TEXT
        );
        """,
    ]

    create_indexes_sql = [
        "CREATE INDEX IF NOT EXISTS index_hosts_on_name ON hosts(name);",
        "CREATE INDEX IF NOT EXISTS index_hosts_on_os_name ON hosts(os_name);",
        "CREATE INDEX IF NOT EXISTS index_hosts_on_state ON hosts(state);",
        "CREATE INDEX IF NOT EXISTS index_services_on_host_id ON services(host_id);",
        "CREATE INDEX IF NOT EXISTS index_services_on_port ON services(port);",
        "CREATE INDEX IF NOT EXISTS index_services_on_name ON services(name);",
        "CREATE INDEX IF NOT EXISTS index_vulns_on_host_id ON vulns(host_id);",
        "CREATE INDEX IF NOT EXISTS index_vulns_on_name ON vulns(name);",
        "CREATE INDEX IF NOT EXISTS index_sessions_on_host_id ON sessions(host_id);",
        "CREATE INDEX IF NOT EXISTS index_sessions_on_stype ON sessions(stype);",
        "CREATE INDEX IF NOT EXISTS index_creds_on_service_id ON creds(service_id);",
        "CREATE INDEX IF NOT EXISTS index_notes_on_host_id ON notes(host_id);",
        "CREATE INDEX IF NOT EXISTS index_loots_on_host_id ON loots(host_id);",
        "CREATE INDEX IF NOT EXISTS index_module_details_on_mtype ON module_details(mtype);",
        "CREATE INDEX IF NOT EXISTS index_module_details_on_name ON module_details(name);",
    ]

    print("=" * 60)
    print("初始化MSF数据库")
    print("=" * 60)

    try:
        connection = psycopg2.connect(**db_config)
        connection.autocommit = True
        cursor = connection.cursor()

        print("\n1. 创建扩展...")
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS plpgsql;")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS hstore;")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
            print("   ✓ 扩展创建成功")
        except Exception as exc:
            print(f"   ! 扩展创建警告: {exc}")

        print("\n2. 创建表结构...")
        for index, sql in enumerate(create_tables_sql):
            try:
                cursor.execute(sql)
                print(f"   ✓ 表 {index + 1}/{len(create_tables_sql)} 创建成功")
            except psycopg2.errors.DuplicateTable:
                print(f"   ! 表 {index + 1}/{len(create_tables_sql)} 已存在")
            except Exception as exc:
                if "already exists" in str(exc):
                    print(f"   ! 表 {index + 1}/{len(create_tables_sql)} 已存在")
                else:
                    print(f"   ✗ 表 {index + 1}/{len(create_tables_sql)} 创建失败: {exc}")

        print("\n3. 创建索引...")
        for index, sql in enumerate(create_indexes_sql):
            try:
                cursor.execute(sql)
                print(f"   ✓ 索引 {index + 1}/{len(create_indexes_sql)} 创建成功")
            except Exception as exc:
                if "already exists" in str(exc):
                    print(f"   ! 索引 {index + 1}/{len(create_indexes_sql)} 已存在")
                else:
                    print(f"   ✗ 索引 {index + 1}/{len(create_indexes_sql)} 创建失败: {exc}")

        print("\n4. 初始化默认工作空间...")
        try:
            cursor.execute("INSERT INTO workspaces (name) SELECT 'default' WHERE NOT EXISTS (SELECT 1 FROM workspaces WHERE name = 'default');")
            print("   ✓ 默认工作空间创建成功")
        except Exception as exc:
            print(f"   ! 工作空间创建警告: {exc}")

        print("\n5. 验证数据库...")
        cursor.execute("SELECT COUNT(*) FROM workspaces;")
        workspace_count = cursor.fetchone()[0]
        print(f"   ✓ 工作空间数量: {workspace_count}")

        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"   ✓ 表数量: {len(tables)}")

        connection.close()
        print("\n" + "=" * 60)
        print("MSF数据库初始化完成!")
        print("=" * 60)
        return True
    except Exception as exc:
        print(f"\n[ERROR] 数据库初始化失败: {exc}")
        import traceback
        traceback.print_exc()
        return False


def _get_model_path():
    """取得當前平台的模型路徑"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    settings_path = os.path.join(base_dir, "src", "core", "ui", "data", "ui_settings.json")
    if os.path.exists(settings_path):
        try:
            import json
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            custom_model_path = settings.get("model_path", "")
            if custom_model_path:
                if os.path.isabs(custom_model_path):
                    if os.path.exists(custom_model_path):
                        print(f"[INFO] Using custom model path from settings: {custom_model_path}")
                        return custom_model_path
                    else:
                        print(f"[WARN] Custom model path not found: {custom_model_path}, falling back to default")
                else:
                    abs_path = os.path.join(base_dir, custom_model_path)
                    if os.path.exists(abs_path):
                        print(f"[INFO] Using custom model path from settings: {abs_path}")
                        return abs_path
                    else:
                        print(f"[WARN] Custom model path not found: {abs_path}, falling back to default")
        except Exception as e:
            print(f"[WARN] Failed to read settings: {e}")
    
    env_model_path = os.environ.get("HUMANIZE2_MODEL_PATH", "")
    if env_model_path and os.path.exists(env_model_path):
        print(f"[INFO] Using model path from environment: {env_model_path}")
        return env_model_path
    
    for model_dir_name in ["model", "models"]:
        model_dir = os.path.join(base_dir, model_dir_name)

        exact_path = os.path.join(model_dir, "tinyllama.gguf")
        if os.path.exists(exact_path):
            return exact_path

        if os.path.exists(model_dir):
            for f in os.listdir(model_dir):
                if f.endswith('.gguf'):
                    return os.path.join(model_dir, f)

    return os.path.join(base_dir, "model", "tinyllama.gguf")


def _is_port_in_use(port: int = 8080) -> bool:
    """检查端口是否被占用"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def _process_is_llama_server(pid: str) -> bool:
    """Return True only for a PID whose command line clearly points to llama-server."""
    if not pid or not str(pid).strip():
        return False

    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}').CommandLine"],
                capture_output=True, text=True, timeout=5
            )
            cmdline = (result.stdout or "") + (result.stderr or "")
        else:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "args="],
                capture_output=True, text=True, timeout=5
            )
            cmdline = (result.stdout or "") + (result.stderr or "")

        return "llama-server" in cmdline.lower()
    except Exception:
        return False


def _kill_process_on_port(port: int = 8080) -> bool:
    """Only terminate llama-server processes that are actually holding the port."""
    killed_any = False

    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ['netstat', '-ano', '-p', 'tcp'],
                capture_output=True,
                text=True
            )
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if f':{port}' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = parts[-1]
                            if not _process_is_llama_server(pid):
                                print(f"[INFO] Port {port} occupied by non-llama-server PID {pid}; leaving it alone.")
                                continue
                            try:
                                subprocess.run(
                                    ['taskkill', '/F', '/PID', pid],
                                    capture_output=True,
                                    text=True
                                )
                                print(f"[INFO] Killed llama-server PID {pid} on port {port}")
                                killed_any = True
                            except:
                                pass
                return killed_any
        except:
            pass
    else:
        try:
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True,
                text=True
            )
            if result.stdout:
                pids = [pid for pid in result.stdout.strip().split('\n') if pid.strip()]
                for pid in pids:
                    if not _process_is_llama_server(pid):
                        print(f"[INFO] Port {port} occupied by non-llama-server PID {pid}; leaving it alone.")
                        continue
                    try:
                        subprocess.run(['kill', '-9', pid], check=True)
                        print(f"[INFO] Killed llama-server PID {pid} on port {port}")
                        killed_any = True
                    except:
                        pass
                return killed_any
        except:
            pass

        try:
            result = subprocess.run(
                ['ss', '-tlnp', f'sport = :{port}'],
                capture_output=True,
                text=True
            )
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) > 5:
                        pid_info = parts[5]
                        if '=' in pid_info:
                            pid = pid_info.split('=')[1].split(',')[0]
                            if not _process_is_llama_server(pid):
                                print(f"[INFO] Port {port} occupied by non-llama-server PID {pid}; leaving it alone.")
                                continue
                            try:
                                subprocess.run(['kill', '-9', pid], check=True)
                                print(f"[INFO] Killed llama-server PID {pid} on port {port}")
                                killed_any = True
                            except:
                                pass
                return killed_any
        except:
            pass

    return False


def _detect_hardware() -> Dict:
    """检测GPU和系统内存，返回硬件信息用于调整启动参数"""
    import shutil as _shutil

    result = {
        "has_gpu": False,
        "gpu_type": None,
        "vram_mb": 0,
        "ram_total_gb": 0,
        "ram_free_gb": 0,
        "llama_dir": "",
    }

    llama_dir = os.path.dirname(_get_llama_server_path())
    result["llama_dir"] = llama_dir

    # 检查 llama 后端 DLL（cuda / vulkan / hip / metal）
    gpu_backends = [
        ("ggml-cuda.dll", "cuda"),
        ("ggml-vulkan.dll", "vulkan"),
        ("ggml-hip.dll", "hip"),
        ("ggml-metal.dll", "metal"),
    ]
    for dll_name, gpu_type in gpu_backends:
        if os.path.exists(os.path.join(llama_dir, dll_name)):
            result["has_gpu"] = True
            result["gpu_type"] = gpu_type
            break

    # 用 nvidia-smi 做更准确的检测（含显存大小）
    if not result["has_gpu"]:
        nvidia_smi = _shutil.which("nvidia-smi")
        if nvidia_smi:
            try:
                proc = subprocess.run(
                    [nvidia_smi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    result["has_gpu"] = True
                    result["gpu_type"] = "cuda"
                    result["vram_mb"] = int(proc.stdout.strip().split('\n')[0].strip())
            except Exception:
                pass

    # 检查系统内存
    try:
        import psutil
        mem = psutil.virtual_memory()
        result["ram_total_gb"] = round(mem.total / (1024**3), 1)
        result["ram_free_gb"] = round(mem.available / (1024**3), 1)
    except Exception:
        try:
            proc = subprocess.run(["free", "-b"], capture_output=True, text=True, timeout=3)
            if proc.returncode == 0:
                lines = proc.stdout.strip().split('\n')
                if len(lines) >= 2:
                    parts = lines[1].split()
                    if len(parts) >= 2:
                        result["ram_total_gb"] = round(int(parts[1]) / (1024**3), 1)
                        if len(parts) >= 7:
                            result["ram_free_gb"] = round(int(parts[6]) / (1024**3), 1)
        except Exception:
            pass

    return result


def _build_llm_args(server_path, model_path, hw_info, ctx_size=4096, max_tokens=256):
    """根据硬件情况构建 llama-server 启动参数"""
    ngl = 999 if hw_info.get("has_gpu", False) else 0
    return [
        server_path, "-m", model_path,
        "-c", str(ctx_size),
        "-ngl", str(ngl),
        "--host", "127.0.0.1",
        "--port", "8080",
        "-n", str(max_tokens),
    ]


def _check_and_start_server(max_wait: int = 120, force_restart: bool = False) -> bool:
    """檢查LLM伺服器是否執行，若未執行則自動啟動，並等待伺服器完全啟動
    
    Args:
        max_wait: 最大等待时间（秒）
        force_restart: 是否强制重启服务器（用于模型切换）
    """
    from tools.tools import check_llm_server
    import time

    print("[INFO] Checking LLM server...")

    target_model_path = _get_model_path()
    model_name = os.path.basename(target_model_path)

    # 检测硬件
    hw_info = _detect_hardware()
    hw_desc = f"GPU: {'Yes (' + hw_info['gpu_type'] + ')' if hw_info['has_gpu'] else 'No'}"
    if hw_info.get("vram_mb", 0) > 0:
        hw_desc += f", VRAM: {hw_info['vram_mb']} MB"
    if hw_info.get("ram_total_gb", 0) > 0:
        hw_desc += f", RAM: {hw_info['ram_total_gb']} GB (free: {hw_info['ram_free_gb']} GB)"

    print("=" * 60)
    print(f"[MODEL] Model Name: {model_name}")
    print(f"[MODEL] Model Path: {target_model_path}")
    print(f"[MODEL] File Exists: {'Yes' if os.path.exists(target_model_path) else 'No'}")
    print(f"[HARDWARE] {hw_desc}")
    print("=" * 60)

    if check_llm_server() and not force_restart:
        print("[INFO] LLM server is already running.")
        return True

    if _is_port_in_use(8080):
        print("[WARN] Port 8080 is occupied")
        print("[INFO] Attempting to clear port and restart...")
        if _kill_process_on_port(8080):
            time.sleep(2)
        else:
            print("[ERROR] Failed to clear port 8080")
            return False

    print("[INFO] Starting LLM server...")

    server_path = _get_llama_server_path()
    model_path = target_model_path

    if not os.path.exists(server_path):
        print("[ERROR] llama-server not found at:", server_path)
        print("[INFO] Please download llama-server from https://github.com/ggerganov/llama.cpp/releases")
        print("[INFO] Place the binary in:", os.path.dirname(server_path))
        return False

    if not os.path.exists(model_path):
        print("[ERROR] Model file not found at:", model_path)
        return False

    # 将 llama-server 的输出写入日志文件，便于诊断崩溃原因
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_dir = os.path.join(project_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    server_log_path = os.path.join(log_dir, "llama_server.log")

    # CPU 模式下，根据内存情况调整参数
    # 模型文件大小（GB）作为粗略参考
    model_size_gb = 0
    try:
        model_size_gb = os.path.getsize(model_path) / (1024**3)
    except Exception:
        pass

    # 候选参数方案：(ctx_size, max_tokens, 描述)
    if hw_info.get("has_gpu", False):
        configs = [
            (4096, 256, "GPU 模式 - 标准参数"),
        ]
    else:
        # CPU 模式：逐级降级
        free_ram_gb = hw_info.get("ram_free_gb", 0)
        if model_size_gb > 0 and free_ram_gb > 0:
            # 模型 > 可用内存时，必须大幅降低上下文
            if model_size_gb > free_ram_gb * 0.9:
                print(f"[WARN] 模型大小 ({model_size_gb:.1f} GB) 接近或超过可用内存 ({free_ram_gb:.1f} GB)，将使用最小参数")
                configs = [
                    (512, 64, "CPU 模式 - 内存不足，最小参数"),
                    (1024, 64, "CPU 模式 - 低内存参数"),
                    (2048, 128, "CPU 模式 - 保守参数"),
                ]
            elif model_size_gb > free_ram_gb * 0.7:
                configs = [
                    (1024, 64, "CPU 模式 - 内存紧张"),
                    (2048, 128, "CPU 模式 - 低内存参数"),
                    (4096, 256, "CPU 模式 - 标准参数"),
                ]
            else:
                configs = [
                    (2048, 128, "CPU 模式 - 保守参数"),
                    (4096, 256, "CPU 模式 - 标准参数"),
                ]
        else:
            configs = [
                (2048, 128, "CPU 模式 - 保守参数"),
                (4096, 256, "CPU 模式 - 标准参数"),
            ]

    last_error_log = ""
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

    for cfg_idx, (ctx_size, max_tokens, cfg_desc) in enumerate(configs):
        print(f"[INFO] Attempt {cfg_idx + 1}/{len(configs)}: {cfg_desc} (ctx={ctx_size}, n={max_tokens})")

        # 写日志文件
        server_log_file = open(server_log_path, "w", encoding="utf-8")

        args = _build_llm_args(server_path, model_path, hw_info, ctx_size, max_tokens)

        try:
            process = subprocess.Popen(
                args,
                cwd=os.path.dirname(server_path),
                stdout=server_log_file,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )

            print(f"[INFO] Waiting for LLM server to start (ctx={ctx_size})...")
            for attempt in range(max_wait):
                time.sleep(1)

                if process.poll() is not None:
                    print("[ERROR] LLM server crashed on startup")
                    server_log_file.flush()
                    server_log_file.close()

                    # 读取日志
                    try:
                        with open(server_log_path, "r", encoding="utf-8", errors="replace") as f:
                            log_content = f.read().strip()
                        if log_content:
                            last_error_log = log_content
                            print("[ERROR] ---- llama-server output ----")
                            print(log_content[-3000:])
                            print("[ERROR] ---- end of output ----")
                        print(f"[INFO] Full log saved to: {server_log_path}")
                    except Exception as read_err:
                        print(f"[ERROR] Failed to read server log: {read_err}")

                    # 检测是否为内存不足错误，决定是否重试
                    is_oom = any(kw in log_content.lower() for kw in [
                        "out of memory", "oom", "failed to allocate",
                        "cannot allocate", "memory", "unable to fit",
                        "fatal", "alloc",
                    ])
                    if is_oom and cfg_idx < len(configs) - 1:
                        print(f"[WARN] Memory allocation failed, retrying with lower parameters...")
                        # 清理端口
                        if _is_port_in_use(8080):
                            _kill_process_on_port(8080)
                            time.sleep(1)
                        continue
                    return False

                if check_llm_server():
                    print(f"[INFO] LLM server started successfully! (ctx={ctx_size})")
                    server_log_file.close()
                    return True

                if (attempt + 1) % 10 == 0:
                    print(f"[INFO] Waiting for LLM server... ({attempt + 1}/{max_wait}s)")

            # 超时
            print("[ERROR] LLM server failed to start within timeout.")
            process.terminate()
            server_log_file.close()

            if cfg_idx < len(configs) - 1:
                print(f"[WARN] Timeout with current config, trying lower parameters...")
                if _is_port_in_use(8080):
                    _kill_process_on_port(8080)
                    time.sleep(1)
                continue
            return False

        except Exception as e:
            server_log_file.close()
            print(f"[ERROR] Failed to start server: {e}")
            if cfg_idx < len(configs) - 1:
                continue
            return False

    # 所有配置都失败
    if last_error_log:
        print("[ERROR] All startup attempts failed. Last error output shown above.")
        print(f"[INFO] Suggestion: The model ({model_size_gb:.1f} GB) may be too large for available RAM.")
        print(f"[INFO] Try a smaller model or a lower quantization level.")
    return False


def _read_ascii():
    ascii_path = os.path.join(os.path.dirname(__file__), "ascii.txt")
    try:
        with open(ascii_path, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return ""


def _auto_start_iot_network():
    """在後台自動啟動 IoT 算力網絡（如果配置啟用）"""
    def _start():
        try:
            settings_path = os.path.join(os.path.dirname(__file__), "ui", "data", "ui_settings.json")
            
            # 讀取配置
            import json
            settings = {}
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            
            auto_start = settings.get("iot_auto_start", True)
            if not auto_start:
                return
            
            host = settings.get("iot_host", "0.0.0.0")
            port = settings.get("iot_port", 8765)
            scan_enabled = settings.get("iot_scan_enabled", True)
            scan_interval = settings.get("iot_scan_interval", 30)
            
            from tools.iot_compute_manager import start_iot_network
            manager = start_iot_network(host=host, port=port)
            print(f"[IoT] 算力網絡後台啟動成功: ws://{host}:{port}")
            
            # 啟動設備掃描
            if scan_enabled:
                from tools.iot_device_scanner import IoTDeviceScanner
                scanner = IoTDeviceScanner(port=port, scan_interval=scan_interval)
                
                # 保存掃描到的設備到配置
                def on_device_found(device):
                    saved = settings.get("iot_discovered_devices", [])
                    saved_ids = {d.get("ip") for d in saved}
                    if device.get("ip") not in saved_ids:
                        saved.append(device)
                        settings["iot_discovered_devices"] = saved
                        try:
                            with open(settings_path, 'w', encoding='utf-8') as f:
                                json.dump(settings, f, indent=4, ensure_ascii=False)
                        except Exception:
                            pass
                
                scanner.on_device_found(on_device_found)
                scanner.start_scanning()
                print(f"[IoT] 設備掃描已啟動（間隔: {scan_interval}s）")
            
        except ImportError as e:
            logger.debug(f"IoT network dependencies not available: {e}")
        except Exception as e:
            logger.error(f"Auto start IoT network failed: {e}")
    
    thread = threading.Thread(target=_start, daemon=True)
    thread.start()


def boot_cli():
    _check_and_start_server()
    _auto_start_iot_network()
    from ui.cli import HumanaizeCLI
    cli = HumanaizeCLI()
    cli.run()


def boot_web_dashboard():
    """启动本地服务并打开浏览器管理面板。"""
    _check_and_start_server()
    _auto_start_iot_network()
    _check_updates_background()

    from memory.memory import load_memory
    try:
        from core.personality import load_personality
        from core.thinking_engine import ThinkingEngine
    except ImportError:
        from personality import load_personality
        from thinking_engine import ThinkingEngine
    from thinking_engine_api import ThinkingEngineState, start_api_server
    import webbrowser
    import time

    memory = load_memory()
    personality = load_personality()
    thinking_engine = ThinkingEngine()
    thinking_engine.set_language("zh")
    state = ThinkingEngineState()
    state.set_thinking_engine(thinking_engine)
    state.set_memory(memory)
    state.set_personality(personality)
    server = start_api_server(host="127.0.0.1", port=8082)
    dashboard_url = f"http://{server.host}:{server.port}/"
    print(f"[INFO] Browser dashboard started: {dashboard_url}")
    webbrowser.open(dashboard_url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()


def _check_updates_background():
    """后台检查更新并发送通知"""
    import threading
    from tools.notify import notify_update
    
    def check():
        try:
            from utils.auto_updater import AutoUpdater
            updater = AutoUpdater("https://github.com/A113NWu/Humanaize2-Project.git")
            update_info = updater.check_for_updates()
            
            if update_info.get("has_update"):
                # 使用标准 Release tag 名（vX.X.X）传给通知和显示
                current_tag = update_info.get("current_tag") or updater._format_release_tag(update_info["current_version"])
                latest_tag = update_info.get("latest_tag") or updater._format_release_tag(update_info["latest_version"])
                notify_update(latest_tag, current_tag)
        except Exception:
            pass
    
    thread = threading.Thread(target=check, daemon=True)
    thread.start()


def boot_gui():
    _check_and_start_server()
    _auto_start_iot_network()
    
    # 后台检查更新
    _check_updates_background()
    
    import warnings
    warnings.filterwarnings("ignore")
    
    import os
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
    
    try:
        import tensorflow as tf
        tf.get_logger().setLevel('ERROR')
    except:
        pass
    
    import customtkinter as ctk
    from ui import HumanaizeUI
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("dark-blue")
    root = ctk.CTk()
    app = HumanaizeUI(root)
    root.mainloop()


def boot_windows_gui():
    """启动 Windows 专属现代化 GUI"""
    _check_and_start_server()
    _auto_start_iot_network()
    
    # 后台检查更新
    _check_updates_background()
    
    import warnings
    warnings.filterwarnings("ignore")
    
    import os
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
    
    try:
        import tensorflow as tf
        tf.get_logger().setLevel('ERROR')
    except:
        pass
    
    import customtkinter as ctk
    from ui.windows_gui import ModernWindowsUI
    root = ctk.CTk()
    app = ModernWindowsUI(root)
    root.mainloop()


def boot_solve(args):
    """啟動問題解決模式"""
    if not _check_and_start_server():
        print("[ERROR] Failed to start LLM server. Exiting...")
        return
    
    _auto_start_iot_network()

    from tools.solve_mode import SolveMode
    
    solver = SolveMode()
    
    problem = ""
    mode_args = []
    
    i = 0
    while i < len(args):
        if args[i].startswith("-"):
            mode_args.append(args[i])
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                mode_args.append(args[i + 1])
                i += 2
                continue
            i += 1
            continue
        if not problem:
            problem = " ".join(args[i:])
        break
    
    solver.parse_args(mode_args)
    
    if not problem.strip():
        print("Enter the problem you want to solve:")
        problem = input("> ")
    
    if not problem.strip():
        print("[ERROR] No problem specified")
        return
    
    solver.set_problem(problem)
    
    try:
        result = solver.run()
    except KeyboardInterrupt:
        print("\n[INFO] Solve mode interrupted")
        solver.stop()


def boot_guard(args):
    """啟動守護模式"""
    background = "--background" in args or "-b" in args
    start_on_boot = "--start-when-boot" in args or "-s" in args
    
    print("[INFO] Starting Guard mode...")
    
    try:
        from tools.guard_mode import GuardMode, guard_mode_api
        
        if background:
            print("[INFO] Running in background mode")
            result = guard_mode_api.start(background=True, start_on_boot=start_on_boot)
            if result.get("status") == "success":
                print("[INFO] Guard mode started successfully in background")
            else:
                print(f"[ERROR] Failed to start Guard mode: {result.get('message')}")
        else:
            print("[INFO] Running in foreground mode (press Ctrl+C to stop)")
            guard = GuardMode(background=False, start_on_boot=start_on_boot)
            guard.start()
                
    except ImportError as e:
        print(f"[ERROR] Failed to import guard_mode module: {e}")
    except Exception as e:
        print(f"[ERROR] Failed to start Guard mode: {e}")


def boot_iot(args):
    """啟動 IoT 算力網絡（獨立於 HSN）"""
    print("[IoT] 正在啟動算力網絡...")
    
    # 解析參數
    host = "0.0.0.0"
    port = 8765
    
    for i, arg in enumerate(args):
        if arg == "--host" and i + 1 < len(args):
            host = args[i + 1]
        elif arg == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
    
    try:
        from tools.iot_compute_manager import start_iot_network
        
        manager = start_iot_network(host=host, port=port)
        
        print(f"[IoT] 算力網絡已啟動")
        print(f"[IoT] WebSocket 地址: ws://{host}:{port}")
        print(f"[IoT] 等待設備連接中...")
        print(f"[IoT] 按 Ctrl+C 停止服務")
        
        # 顯示狀態
        import time
        try:
            while True:
                time.sleep(5)
                stats = manager.get_stats()
                online = stats.get('online_devices', 0)
                total = stats.get('total_devices', 0)
                tasks = stats.get('completed_tasks', 0)
                print(f"[IoT] 狀態: 在線={online}/{total} | 已完成任務={tasks}")
        except KeyboardInterrupt:
            print("\n[IoT] 正在停止算力網絡...")
            from tools.iot_compute_manager import stop_iot_network
            stop_iot_network()
            print("[IoT] 已停止")
            
    except ImportError as e:
        print(f"[ERROR] Failed to import IoT module: {e}")
        print("[INFO] 請安裝 websockets 庫: pip install websockets>=12.0")
    except Exception as e:
        print(f"[ERROR] Failed to start IoT network: {e}")


def open_settings():
    from ui.cli_settings import SettingsCLI
    settings_cli = SettingsCLI()
    settings_cli.run()


def handle_skills():
    from tools.skills_cli import SkillsCLI
    skills_cli = SkillsCLI()
    skills_cli.process_command(["skills"] + sys.argv[2:])


def handle_update(args):
    """Handle update command"""
    from utils.auto_updater import AutoUpdater
    from tools.notify import notify_update, notify_info
    
    force_update = "-f" in args or "--force" in args
    
    updater = AutoUpdater("https://github.com/A113NWu/Humanaize2-Project.git")
    
    def progress_callback(msg):
        print(f"[UPDATE] {msg}")
    
    print("Checking for updates...")
    update_info = updater.check_for_updates()
    
    if update_info.get("error"):
        print(f"[ERROR] Failed to check for updates: {update_info['error']}")
        return
    
    current_tag = update_info.get("current_tag") or updater._format_release_tag(update_info["current_version"])
    latest_tag = update_info.get("latest_tag") or updater._format_release_tag(update_info["latest_version"])
    current_version = update_info["current_version"]
    latest_version = update_info["latest_version"]
    
    print(f"Current version: {current_tag}")
    print(f"Latest release: {latest_tag}")
    
    if update_info.get("release_notes"):
        print(f"\nRelease Notes:\n{update_info['release_notes']}")
    
    if update_info.get("has_update") or force_update:
        # 发送更新通知（使用 vX.X.X 标准标签名）
        if update_info.get("has_update"):
            notify_update(latest_tag, current_tag)
        
        if not update_info.get("has_update"):
            print("\n[INFO] Already up to date, but forcing update...")
        
        print("\nStarting update installation...")
        
        # Try git pull first if available, otherwise download zip
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            )
            is_git_repo = result.returncode == 0
        except:
            is_git_repo = False
        
        if is_git_repo:
            print("[INFO] Git repository detected, using git pull method...")
            result = updater.pull_latest_from_git(progress_callback, force=force_update)
        else:
            print("[INFO] Using download and install method...")
            result = updater.download_and_install_update(progress_callback, force=force_update)
        
        if result.get("success"):
            print(f"\n{result['message']}")
            notify_info("Humanaize 更新完成", f"已更新到版本 {latest_tag}")
        else:
            print(f"\n[ERROR] Update failed: {result.get('error', result.get('message'))}")
    else:
        print("\n[INFO] You are already on the latest version.")
        print("Use 'humanaize2 update -f' to force update.")


def main():
    args = sys.argv[1:]
    
    if not args:
        print(__doc__)
        print("Usage:")
        print("  humanaize2 boot         - Start browser dashboard")
        print("  humanaize2 boot -m cli  - Start CLI chat interface")
        print("  humanaize2 boot -m gui  - Start GUI interface")
        print("  humanaize2 boot -m win-gui  - Start Windows modern GUI interface")
        print("  humanaize2 boot -m solve [--hsn] [--sandbox <dir>] [-gan] - Start problem solving mode")
        print("  humanaize2 boot -m guard [--background] [--start-when-boot] - Start guard mode")
        print("  humanaize2 settings     - Open settings interface")
        print("\nOptions for solve mode:")
        print("  --hsn          Enable HSN (Human Swarm Network)")
        print("  --sandbox <dir>  Enable sandbox mode, restrict AI to specified directory")
        print("  -gan           Enable enhanced GAN mode")
        print("\nOptions for guard mode:")
        print("  --background          Run in background mode")
        print("  --start-when-boot     Enable auto-start on system boot")
        print("\nOr use directly:")
        print("  python main.py boot")
        print("  python main.py boot -m cli")
        print("  python main.py boot -m gui")
        print("  python main.py boot -m win-gui")
        print("  python main.py boot -m solve")
        print("  python main.py boot -m guard")
        print("  python main.py settings")
        return
    
    command = args[0].lower()
    
    speeches = [
        "Android or Apple, this is a question.",
        "I'll never treat my users as a human >_*",
        "I see dead code... Just kidding, it's alive!",
        "I'm a robot, are you a robot?",
        "Talking to a human today. Novel experience!"
    ]
    
    ascii_art = _read_ascii()
    
    if command == "boot":
        # Check for mode parameter
        mode = None
        mode_args = []
        i = 1
        while i < len(args):
            if args[i] == "-m" or args[i] == "-mode":
                if i + 1 < len(args):
                    mode = args[i + 1].lower()
                    mode_args = args[i + 2:]
                    break
            i += 1
        
        if mode == "cli":
            print("Starting CLI chat interface...")
            boot_cli()
        elif mode == "gui":
            choice = random.randint(0, 4)
            if choice == 3 and ascii_art:
                print(ascii_art)
            else:
                print(speeches[choice])
            print("Starting GUI interface...")
            boot_gui()
        elif mode == "win-gui":
            choice = random.randint(0, 4)
            if choice == 3 and ascii_art:
                print(ascii_art)
            else:
                print(speeches[choice])
            print("Starting Windows modern GUI interface...")
            boot_windows_gui()
        elif mode == "solve":
            choice = random.randint(0, 4)
            if choice == 3 and ascii_art:
                print(ascii_art)
            else:
                print(speeches[choice])
            print("Starting CLI chat interface...")
            print("Starting SOLVE mode...")
            boot_solve(mode_args)
        elif mode == "guard":
            print("Starting Guard mode...")
            boot_guard(mode_args)
        elif mode == "iot":
            print("Starting IoT Compute Network...")
            boot_iot(mode_args)
        else:
            choice = random.randint(0, 4)
            if choice == 3 and ascii_art:
                print(ascii_art)
            else:
                print(speeches[choice])
            print("Starting browser dashboard...")
            boot_web_dashboard()
    elif command == "settings":
        choice = random.randint(0, 4)
        if choice == 3 and ascii_art:
            print(ascii_art)
        else:
            print(speeches[choice])
        print("Opening settings interface...")
        open_settings()
    elif command == "skills":
        handle_skills()
    elif command == "update":
        choice = random.randint(0, 4)
        if choice == 3 and ascii_art:
            print(ascii_art)
        else:
            print(speeches[choice])
        handle_update(args[1:])
    else:
        print(f"Unknown command: {command}")
        print("Usage:")
        print("  humanaize2 boot         - Start browser dashboard")
        print("  humanaize2 boot -m cli  - Start CLI chat interface")
        print("  humanaize2 boot -m gui  - Start GUI interface")
        print("  humanaize2 boot -m solve [--hsn] [--sandbox <dir>] [-gan] - Start problem solving mode")
        print("  humanaize2 boot -m iot [--host <ip>] [--port <n>] - Start IoT compute network")
        print("  humanaize2 settings     - Open settings interface")
        print("  humanaize2 skills      - Manage skills")
        print("  humanaize2 update      - Check for and install updates")
        print("  humanaize2 update -f   - Force update even if already up to date")


if __name__ == "__main__":
    main()