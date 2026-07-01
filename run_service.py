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
    """이미 실행 중인 프로세스가 있으면 종료."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                old_pid = int(f.read().strip())
            # Windows: pid 존재 여부 확인
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, old_pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                print(f"[LOCK] 이미 실행 중인 프로세스 감지 (PID {old_pid}). 종료합니다.")
                sys.exit(1)
        except Exception:
            pass  # 이전 프로세스가 없거나 읽기 실패 → 덮어쓰기
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(_release_lock)


def _release_lock():
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass


from pipeline.scheduler import main

if __name__ == "__main__":
    _acquire_lock()
    main()
