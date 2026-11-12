@echo off
chcp 65001 >nul
rem 윈도에서 더블클릭으로 모델 시험을 실행하는 파일
cd /d "%~dp0"

if not exist ".env" (
  echo [실패] 이 폴더에 .env 파일이 없습니다.
  echo        메모장으로 아래 한 줄을 적고 .env 라는 이름으로 저장하세요.
  echo        OPENROUTER_API_KEY=sk-or-v1-본인키
  echo.
  pause
  exit /b 1
)

echo [1/2] 필요한 꾸러미를 설치합니다 ^(처음 한 번만 시간이 걸립니다^)
python -m pip install --quiet requests pillow
if errorlevel 1 (
  echo [실패] 파이썬을 찾지 못했습니다. python.org 에서 설치하고 다시 실행하세요.
  pause
  exit /b 1
)

echo [2/2] 모델 시험을 시작합니다
echo.
python test_openrouter.py

echo.
echo 창을 닫으려면 아무 키나 누르세요.
pause >nul
