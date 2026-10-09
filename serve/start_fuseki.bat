@echo off
REM Khởi động Fuseki trên Windows với cấu hình của project.
REM Cần: Java 17+ và Apache Jena Fuseki đã giải nén (xem README.md).
REM Cách dùng (trong cmd):
REM     set FUSEKI_HOME=C:\tools\apache-jena-fuseki-X.Y.Z
REM     serve\start_fuseki.bat
REM Để cửa sổ này mở trong suốt thời gian dùng endpoint.
chcp 65001 >nul
cd /d "%~dp0"
where java >nul 2>nul || (echo Chua co Java. Cai Java 17 tro len, vi du Eclipse Temurin 21: https://adoptium.net & exit /b 1)
if "%FUSEKI_HOME%"=="" (echo Chua dat FUSEKI_HOME. Vi du: set FUSEKI_HOME=C:\tools\apache-jena-fuseki-X.Y.Z & exit /b 1)
if not exist "%FUSEKI_HOME%\fuseki-server.bat" (echo Khong thay "%FUSEKI_HOME%\fuseki-server.bat". Kiem tra lai FUSEKI_HOME. & exit /b 1)
call "%FUSEKI_HOME%\fuseki-server.bat" --config=config.ttl
