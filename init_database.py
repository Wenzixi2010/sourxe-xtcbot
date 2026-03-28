#!/usr/bin/env python3

import yaml
import pymysql
from pymysql import Error

def load_config():
    try:
        with open('config.yaml', 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        return config
    except Exception as e:
        print(f"加载配置文件失败：{e}")
        return {}

def get_mysql_config():
    config = load_config()
    mysql_config = config.get('mysql_config', {})
    required_fields = ['host', 'port', 'user', 'password', 'database']
    for field in required_fields:
        if field not in mysql_config:
            raise ValueError(f"Config配置文件中缺少MySQL必要的字段: {field}")
    return {
        'host': mysql_config['host'],
        'port': mysql_config['port'],
        'user': mysql_config['user'],
        'password': mysql_config['password'],
        'database': mysql_config['database'],
        'charset': mysql_config.get('charset', 'utf8mb4'),
        'cursorclass': pymysql.cursors.DictCursor
    }

def check_and_fix_tables():
    try:
        config = get_mysql_config()
        conn = pymysql.connect(**config)
        
        with conn.cursor() as cursor:
            print("=" * 50)
            print("开始检查数据库表结构...")
            print("=" * 50)
            
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            table_names = [table['Tables_in_xtcsql'] for table in tables] if tables else []
            print(f"当前数据库中的表：{table_names}")
            
            print("\n1. 检查user_info表...")
            # 修改role字段，添加donor和advanced值
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_info (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL UNIQUE,
                    role ENUM('user', 'admin', 'donor', 'advanced') DEFAULT 'user',
                    allow_addme BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP NULL,
                    INDEX idx_user_id (user_id),
                    INDEX idx_role (role),
                    INDEX idx_allow_addme (allow_addme)
                )
            ''')
            
            # 检查并更新已存在的表结构
            cursor.execute("DESCRIBE user_info")
            columns = cursor.fetchall()
            
            # 检查role字段是否需要更新
            role_column = next((col for col in columns if col['Field'] == 'role'), None)
            if role_column and ("donor" not in role_column['Type'] or "advanced" not in role_column['Type']):
                print("检测到role字段需要更新，添加donor和advanced值...")
                # 需要先修改字段类型为VARCHAR，再修改回ENUM
                cursor.execute("ALTER TABLE user_info MODIFY COLUMN role VARCHAR(20)")
                cursor.execute("ALTER TABLE user_info MODIFY COLUMN role ENUM('user', 'admin', 'donor', 'advanced') DEFAULT 'user'")
                print("✓ role字段更新成功，添加了donor和advanced值")
            
            if 'allow_addme' not in [col['Field'] for col in columns]:
                print("检测到缺少allow_addme字段，正在添加...")
                cursor.execute("ALTER TABLE user_info ADD COLUMN allow_addme BOOLEAN DEFAULT TRUE")
                cursor.execute("ALTER TABLE user_info ADD INDEX idx_allow_addme (allow_addme)")
                print("✓ allow_addme字段添加成功")
            else:
                print("✓ allow_addme字段已存在")
            
            print("\n2. 检查devices_info表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS devices_info (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    watchid VARCHAR(255),
                    chipid VARCHAR(255),
                    bindnumber VARCHAR(255),
                    model VARCHAR(255),
                    imaccountid VARCHAR(255),
                    INDEX idx_user_id (user_id),
                    INDEX idx_watchid (watchid),
                    INDEX idx_chipid (chipid),
                    INDEX idx_imaccountid (imaccountid),
                    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE CASCADE
                )
            ''')
            
            # 检查并更新已存在的表结构，添加imaccountid字段
            cursor.execute("DESCRIBE devices_info")
            devices_columns = cursor.fetchall()
            
            if 'imaccountid' not in [col['Field'] for col in devices_columns]:
                print("检测到缺少imaccountid字段，正在添加...")
                cursor.execute("ALTER TABLE devices_info ADD COLUMN imaccountid VARCHAR(255)")
                cursor.execute("ALTER TABLE devices_info ADD INDEX idx_imaccountid (imaccountid)")
                print("✓ imaccountid字段添加成功")
            else:
                print("✓ imaccountid字段已存在")
                
            print("✓ devices_info表检查完成")
            
            print("\n3. 检查likeall_tasks表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS likeall_tasks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    status ENUM('queued', 'processing', 'completed', 'failed') DEFAULT 'queued',
                    message VARCHAR(255),
                    success_count INT DEFAULT 0,
                    total_count INT DEFAULT 0,
                    queue_position INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP NULL,
                    completed_at TIMESTAMP NULL,
                    INDEX idx_user_id (user_id),
                    INDEX idx_status (status),
                    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE CASCADE
                )
            ''')
            print("✓ likeall_tasks表检查完成")
            
            print("\n4. 检查activation_codes表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activation_codes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    code VARCHAR(32) NOT NULL UNIQUE,
                    code_type ENUM('donor', 'advanced') DEFAULT 'donor',
                    status ENUM('active', 'used') DEFAULT 'active',
                    used_by VARCHAR(255),
                    used_at TIMESTAMP NULL,
                    created_by VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NULL,
                    INDEX idx_code (code),
                    INDEX idx_code_type (code_type),
                    INDEX idx_status (status),
                    INDEX idx_used_by (used_by),
                    INDEX idx_created_by (created_by),
                    INDEX idx_expires_at (expires_at)
                )
            ''')
            
            # 检查并更新已存在的表结构
            cursor.execute("DESCRIBE activation_codes")
            activation_columns = cursor.fetchall()
            
            if 'code_type' not in [col['Field'] for col in activation_columns]:
                print("检测到缺少code_type字段，正在添加...")
                cursor.execute("ALTER TABLE activation_codes ADD COLUMN code_type ENUM('donor', 'advanced') DEFAULT 'donor'")
                cursor.execute("ALTER TABLE activation_codes ADD INDEX idx_code_type (code_type)")
                print("✓ code_type字段添加成功")
            else:
                print("✓ code_type字段已存在")
                
            print("✓ activation_codes表检查完成")
            
            conn.commit()
            
            print("\n" + "=" * 50)
            print("数据库表结构检查完成！")
            print("=" * 50)
            
            cursor.execute("SHOW TABLES")
            final_tables = cursor.fetchall()
            final_table_names = [table['Tables_in_xtcsql'] for table in final_tables] if final_tables else []
            print(f"最终数据库表：{final_table_names}")
            
            print("\nuser_info表结构：")
            cursor.execute("DESCRIBE user_info")
            user_info_columns = cursor.fetchall()
            for column in user_info_columns:
                print(f"  {column['Field']} - {column['Type']} - {column['Null']} - {column['Default']}")
            
            print("\ndevices_info表结构：")
            cursor.execute("DESCRIBE devices_info")
            devices_info_columns = cursor.fetchall()
            for column in devices_info_columns:
                print(f"  {column['Field']} - {column['Type']} - {column['Null']} - {column['Default']}")
            
    except Error as e:
        print(f"数据库操作失败：{e}")
    except Exception as e:
        print(f"初始化失败：{e}")
    finally:
        if 'conn' in locals():
            conn.close()

def test_database_connection():
    try:
        config = get_mysql_config()
        conn = pymysql.connect(**config)
        print("✓ 数据库连接测试成功")
        conn.close()
        return True
    except Exception as e:
        print(f"✗ 数据库连接测试失败：{e}")
        return False

def main():
    print("数据库初始化脚本启动...")
    
    if not test_database_connection():
        print("无法连接到数据库，请检查配置")
        return
    
    check_and_fix_tables()
    
    print("\n初始化完成！现在可以正常启动机器人了。")

if __name__ == "__main__":
    main()