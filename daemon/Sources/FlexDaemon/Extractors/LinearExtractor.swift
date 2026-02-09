import Foundation

struct LinearExtractor: AppExtractor {
    let bundleId = "com.linear"
    let processName = "Linear"

    func extractContent(pid: pid_t) -> [ExtractedItem] {
        let windowTitle = AXTreeHelper.windowTitle(pid: pid) ?? "Linear"
        let tree = AXTreeHelper.getTextTree(pid: pid)
        guard !tree.isEmpty else { return [] }
        return [ExtractedItem(text: tree, contextId: "linear", context: windowTitle)]
    }
}
