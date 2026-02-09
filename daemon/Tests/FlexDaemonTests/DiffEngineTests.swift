import XCTest
@testable import FlexDaemon

final class DiffEngineTests: XCTestCase {
    private func makeEngine() -> DiffEngine {
        DiffEngine(withoutPersistence: true)
    }

    func testFirstTimeSeeingContextReturnsNew() {
        let engine = makeEngine()
        let item = ExtractedItem(text: "Hello world", contextId: "test-1", context: "Test")
        let result = engine.diff(bundleId: "com.test", item: item)

        XCTAssertNotNil(result)
        XCTAssertEqual(result?.outputText, "Hello world")
        XCTAssertEqual(result?.changeType, .new)
    }

    func testUnchangedContentReturnsNil() {
        let engine = makeEngine()
        let item = ExtractedItem(text: "Hello world", contextId: "test-1", context: "Test")

        _ = engine.diff(bundleId: "com.test", item: item)
        let result = engine.diff(bundleId: "com.test", item: item)

        XCTAssertNil(result)
    }

    func testAppendedContentReturnsDelta() {
        let engine = makeEngine()
        let item1 = ExtractedItem(text: "Message 1\nMessage 2", contextId: "test-1", context: "Test")
        let item2 = ExtractedItem(text: "Message 1\nMessage 2\nMessage 3", contextId: "test-1", context: "Test")

        _ = engine.diff(bundleId: "com.test", item: item1)
        let result = engine.diff(bundleId: "com.test", item: item2)

        XCTAssertNotNil(result)
        XCTAssertEqual(result?.outputText, "Message 3")
        XCTAssertEqual(result?.changeType, .appended)
    }

    func testChangedContentReturnsFullContent() {
        let engine = makeEngine()
        let item1 = ExtractedItem(text: "Channel: general\nMessage 1", contextId: "test-1", context: "Test")
        let item2 = ExtractedItem(text: "Channel: random\nMessage A", contextId: "test-1", context: "Test")

        _ = engine.diff(bundleId: "com.test", item: item1)
        let result = engine.diff(bundleId: "com.test", item: item2)

        XCTAssertNotNil(result)
        XCTAssertEqual(result?.outputText, "Channel: random\nMessage A")
        XCTAssertEqual(result?.changeType, .changed)
    }

    func testDifferentContextsTrackedSeparately() {
        let engine = makeEngine()
        let item1 = ExtractedItem(text: "Content A", contextId: "ctx-1", context: "Test 1")
        let item2 = ExtractedItem(text: "Content B", contextId: "ctx-2", context: "Test 2")

        let result1 = engine.diff(bundleId: "com.test", item: item1)
        let result2 = engine.diff(bundleId: "com.test", item: item2)

        XCTAssertNotNil(result1)
        XCTAssertNotNil(result2)
        XCTAssertEqual(result1?.changeType, .new)
        XCTAssertEqual(result2?.changeType, .new)
    }

    func testEmptyContentReturnsNil() {
        let engine = makeEngine()
        let item = ExtractedItem(text: "", contextId: "test-1", context: "Test")
        let result = engine.diff(bundleId: "com.test", item: item)

        XCTAssertNil(result)
    }

    func testDifferentBundleIdsSeparateTracking() {
        let engine = makeEngine()
        let item = ExtractedItem(text: "Same content", contextId: "ctx-1", context: "Test")

        let result1 = engine.diff(bundleId: "com.app1", item: item)
        let result2 = engine.diff(bundleId: "com.app2", item: item)

        XCTAssertNotNil(result1)
        XCTAssertNotNil(result2)
        XCTAssertEqual(result1?.changeType, .new)
        XCTAssertEqual(result2?.changeType, .new)
    }

    func testAppendWhitespaceOnlyReturnsNil() {
        let engine = makeEngine()
        let item1 = ExtractedItem(text: "Hello", contextId: "test-1", context: "Test")
        let item2 = ExtractedItem(text: "Hello\n  \n", contextId: "test-1", context: "Test")

        _ = engine.diff(bundleId: "com.test", item: item1)
        let result = engine.diff(bundleId: "com.test", item: item2)

        XCTAssertNil(result)
    }
}
