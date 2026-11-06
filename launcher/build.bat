@echo off
chcp 65001 >nul
rem 用 Windows 自带的 .NET Framework 编译器生成项目根目录下的 富途牛牛.exe
setlocal
cd /d "%~dp0"
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe
"%CSC%" /nologo /target:winexe /codepage:65001 /optimize+ /win32icon:futu.ico ^
  /r:System.Windows.Forms.dll /out:"..\富途牛牛.exe" FutuLauncher.cs
if errorlevel 1 (pause & exit /b 1)
echo 已生成 ..\富途牛牛.exe
