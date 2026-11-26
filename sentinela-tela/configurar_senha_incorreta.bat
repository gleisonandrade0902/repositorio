@echo off
rem ======================================================================
rem  Sentinela de Tela - habilita a foto ao digitarem SENHA INCORRETA.
rem  Execute UMA vez como Administrador (o painel faz isso pelo botao).
rem   1) Liga a auditoria de falha de logon (evento 4625)
rem   2) Cria tarefa SYSTEM que anota cada falha num arquivo que o app le
rem  Para desfazer:  configurar_senha_incorreta.bat remover
rem ======================================================================
net session >nul 2>&1 || (echo Precisa ser executado como Administrador. & pause & exit /b 1)
set PASTA=%ProgramData%\SentinelaTela
set TAREFA=SentinelaTela_FalhaLogin

if /i "%1"=="remover" (
  schtasks /delete /tn %TAREFA% /f
  echo Removido. & pause & exit /b 0
)

mkdir "%PASTA%" 2>nul
type nul >> "%PASTA%\falhas_login.log"
rem Usuarios comuns podem ler; so o SYSTEM escreve.
icacls "%PASTA%" /inheritance:r /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-32-545:(OI)(CI)R" >nul

rem GUID da subcategoria "Logon" (independe do idioma do Windows)
auditpol /set /subcategory:{0CCE9215-69AE-11D9-BED3-505054503030} /failure:enable

schtasks /create /f /tn %TAREFA% /ru SYSTEM /rl HIGHEST /sc ONEVENT /ec Security ^
  /mo "*[System[(EventID=4625)]]" ^
  /tr "cmd /c echo %%date%% %%time%% >>\"%PASTA%\falhas_login.log\""

echo.
echo Pronto! O Sentinela agora fotografa quem errar a senha na tela de bloqueio.
pause
