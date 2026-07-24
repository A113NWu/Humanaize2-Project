#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
初始化MSF数据库表结构
与msfconsole的schema.rb保持兼容
"""

import psycopg2
import psycopg2.errors

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "database": "msf",
    "user": "msf",
    "password": ""
}

CREATE_TABLES_SQL = [
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
    """
]

CREATE_INDEXES_SQL = [
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

def init_database():
    """初始化MSF数据库"""
    print("=" * 60)
    print("初始化MSF数据库")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("\n1. 创建扩展...")
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS plpgsql;")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS hstore;")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
            print("   ✓ 扩展创建成功")
        except Exception as e:
            print(f"   ! 扩展创建警告: {e}")
        
        print("\n2. 创建表结构...")
        for i, sql in enumerate(CREATE_TABLES_SQL):
            try:
                cursor.execute(sql)
                print(f"   ✓ 表 {i+1}/{len(CREATE_TABLES_SQL)} 创建成功")
            except psycopg2.errors.DuplicateTable:
                print(f"   ! 表 {i+1}/{len(CREATE_TABLES_SQL)} 已存在")
            except Exception as e:
                if "already exists" in str(e):
                    print(f"   ! 表 {i+1}/{len(CREATE_TABLES_SQL)} 已存在")
                else:
                    print(f"   ✗ 表 {i+1}/{len(CREATE_TABLES_SQL)} 创建失败: {e}")
        
        print("\n3. 创建索引...")
        for i, sql in enumerate(CREATE_INDEXES_SQL):
            try:
                cursor.execute(sql)
                print(f"   ✓ 索引 {i+1}/{len(CREATE_INDEXES_SQL)} 创建成功")
            except Exception as e:
                if "already exists" in str(e):
                    print(f"   ! 索引 {i+1}/{len(CREATE_INDEXES_SQL)} 已存在")
                else:
                    print(f"   ✗ 索引 {i+1}/{len(CREATE_INDEXES_SQL)} 创建失败: {e}")
        
        print("\n4. 初始化默认工作空间...")
        try:
            cursor.execute("INSERT INTO workspaces (name) SELECT 'default' WHERE NOT EXISTS (SELECT 1 FROM workspaces WHERE name = 'default');")
            print("   ✓ 默认工作空间创建成功")
        except Exception as e:
            print(f"   ! 工作空间创建警告: {e}")
        
        print("\n5. 验证数据库...")
        cursor.execute("SELECT COUNT(*) FROM workspaces;")
        workspace_count = cursor.fetchone()[0]
        print(f"   ✓ 工作空间数量: {workspace_count}")
        
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"   ✓ 表数量: {len(tables)}")
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("MSF数据库初始化完成!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = init_database()
    exit(0 if success else 1)