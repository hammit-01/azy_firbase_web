export const dom = {
    searchInput: null,
    searchField: null,
    sortField: null,
    sortField2: null,
    sortOrder: null,
    listDiv: null,
    container: null,
    sideBox: null
};

export function initDOM() {
    dom.searchInput = document.getElementById("searchInput");
    dom.searchField = document.getElementById("searchField");
    dom.sortField = document.getElementById("sortField");
    dom.sortField2 = document.querySelector("#sortField2"),
    dom.sortOrder = document.getElementById("sortOrder");
    dom.listDiv = document.getElementById("list");
    dom.container = document.querySelector(".container");
    dom.sideBox = document.getElementById("sideBox");
}
