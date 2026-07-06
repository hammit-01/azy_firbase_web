"""
창고 재고 파이프라인 서비스 진입점
실행: python run_service.py
"""
import sys
import os
import atexit

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(__file__))

LOCK_FILE = os.path.join(os.path.dirname(__file__), "pipeline", ".service.lock")


def _acquire_lock():
    """기존 프로세스가 살아 있으면 종료 후 락 획득."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                old_pid = int(f.read().strip())
            import ctypes, signal
            handle = ctypes.windll.kernel32.OpenProcess(0x1001, False, old_pid)  # PROCESS_QUERY+TERMINATE
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                print(f"[LOCK] 기존 프로세스 종료 중 (PID {old_pid})...")
                try:
                    os.kill(old_pid, signal.SIGTERM)
                    import time; time.sleep(2)
                except Exception:
                    pass
                # 여전히 살아 있으면 강제 종료
                handle2 = ctypes.windll.kernel32.OpenProcess(0x1001, False, old_pid)
                if handle2:
                    ctypes.windll.kernel32.TerminateProcess(handle2, 1)
                    ctypes.windll.kernel32.CloseHandle(handle2)
                    print(f"[LOCK] PID {old_pid} 강제 종료 완료")
        except Exception:
            pass  # 락 파일 없거나 읽기 실패 → 무시
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(_release_lock)


def _release_lock():
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass


import threading
import uvicorn

def _run_api():
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, log_level="warning")

from pipeline.scheduler import main

if __name__ == "__main__":
    _acquire_lock()
    # API 서버를 백그라운드 스레드로 실행
    api_thread = threading.Thread(target=_run_api, daemon=True)
    api_thread.start()
    print("[SERVICE] API 서버 시작: http://localhost:8000")
    main()
