export const undoStack = [];

export async function undoLastAction() {

    console.log("before pop", undoStack.length);

    const action = undoStack.pop();

    console.log("action", action);

    if (!action) {
        alert("되돌릴 작업이 없습니다.");
        return;
    }

    try {

        console.log("undo 시작");

        await action.undo();

        console.log("undo 완료");

    } catch (error) {

        console.error("되돌리기 실패:", error);

    }
}