@echo off
REM 安装 PostgreSQL 16 并创建 ai_interviewer 数据库
REM 以管理员身份运行

echo ============================================
echo  正在安装 PostgreSQL 16 for Windows
echo ============================================

REM 检查是否已安装
where psql >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo PostgreSQL 已安装，跳过安装步骤
    goto :createdb
)

REM 下载 PostgreSQL 安装程序
echo 正在下载 PostgreSQL 安装程序...
curl -L -o %TEMP%\postgresql-16.4-1-windows-x64.exe "https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64.exe"

REM 静默安装
echo 正在安装 PostgreSQL（静默安装，密码为 postgres）...
start /wait "" "%TEMP%\postgresql-16.4-1-windows-x64.exe" --mode unattended --superpassword postgres --servicename postgresql-x64-16 --serverport 5432

REM 等待服务启动
echo 等待 PostgreSQL 服务启动...
timeout /t 5 /nobreak >nul

:createdb
REM 创建数据库
echo 正在创建数据库 ai_interviewer...
"C:\Program Files\PostgreSQL\16\bin\psql" -U postgres -c "CREATE DATABASE ai_interviewer;" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo 数据库创建成功！
) else (
    echo 数据库可能已存在，跳过创建
)

REM 显示连接信息
echo.
echo ============================================
echo  数据库连接信息
echo ============================================
echo  主机: localhost
echo  端口: 5432
echo  数据库: ai_interviewer
echo  用户名: postgres
echo  密码: postgres
echo.
echo  请在 server/.env 中添加:
echo  DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_interviewer
echo.
echo ============================================
pause