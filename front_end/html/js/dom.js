export const dom = {
    searchInput: null,
    searchInput2: null,
    searchField: null,
    sortField: null,
    sortOrder: null,
    listDiv: null,
    insertRowsBody: null,
    container: null,
    sideBox: null
};

export function initDOM() {
    dom.searchInput = document.getElementById("searchInput");
    dom.searchInput2 = document.getElementById("searchInput2");
    dom.searchField = document.getElementById("searchField");
    dom.sortField = document.getElementById("sortField");
    dom.sortOrder = document.getElementById("sortOrder");
    dom.listDiv = document.getElementById("list");
    dom.insertRowsBody = document.getElementById("insert-rows");
    dom.container = document.querySelector(".container");
    dom.sideBox = document.getElementById("sideBox");
}
