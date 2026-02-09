import Foundation

struct SlackExtractor: AppExtractor {
    let bundleId = "com.tinyspeck.slackmacgap"
    let processName = "Slack"

    func extractContent(pid: pid_t) -> [ExtractedItem] {
        let windowTitle = AXTreeHelper.windowTitle(pid: pid) ?? "Slack"
        let tree = AXTreeHelper.getTextTree(pid: pid)
        guard !tree.isEmpty else { return [] }
        return [ExtractedItem(text: tree, contextId: "slack", context: windowTitle)]
    }
}
