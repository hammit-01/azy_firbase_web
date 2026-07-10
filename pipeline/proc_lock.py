"""단일 인스턴스 보장용 PID 락 파일 유틸리티 (Windows 프로세스 종료 포함).
run_service.py(파이프라인)와 run_api.py(API 서버)가 각자 독립된 락 파일로 공유한다."""
import os
import atexit


def acquire(lock_file: str, label: str = "프로세스"):
    """기존 프로세스가 살아 있으면 종료 후 락 획득."""
    if os.path.exists(lock_file):
        try:
            with open(lock_file) as f:
                old_pid = int(f.read().strip())
            import ctypes, signal, time
            handle = ctypes.windll.kernel32.OpenProcess(0x1001, False, old_pid)  # PROCESS_QUERY+TERMINATE
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                print(f"[LOCK] 기존 {label} 종료 중 (PID {old_pid})...")
                try:
                    os.kill(old_pid, signal.SIGTERM)
                    time.sleep(2)
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
    with open(lock_file, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(_release, lock_file)


def _release(lock_file: str):
    try:
        os.remove(lock_file)
    except FileNotFoundError:
        pass
