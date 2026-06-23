export const undoStack = [];

export async function undoLastAction() {
    const action = undoStack.pop();

    if (!action) {
        alert("되돌릴 작업이 없습니다.");
        return;
    }

    try {
        await action.undo();
    } catch (error) {
        console.error("되돌리기 실패:", error);
    }
}
