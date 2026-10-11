import XCTest

/// Runs against the app's in-process fake gateway (`-fakeGateway YES`) with a fake APNs token, so it
/// needs no server and cannot reach a live host. Sample screens come from `-state <name>`.
final class PairingFlowUITests: XCTestCase {
    private let link = "canarito://pair?v=1&server=http%3A%2F%2Flocalhost%3A1&secret=\(String(repeating: "3f", count: 16))"
        + "&relay=http%3A%2F%2Flocalhost%3A2&sid=\(String(repeating: "a1", count: 16))"

    /// First run on a clean install: intro, the system prompts, paste a link, confirm, covered.
    /// Run after `xcrun simctl uninstall <udid> app.canarito`.
    func testFirstRunToCoveredWithAPastedLink() throws {
        let app = XCUIApplication()
        app.launchArguments += ["-fakeGateway", "YES", "-fakeToken", "YES", "-AppleLanguages", "(es)"]
        app.launch()
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")

        // A phone that already saw the intro goes straight to pairing; a clean install starts here.
        let next = app.buttons["continue"]
        if next.waitForExistence(timeout: 20) {
            XCTAssertFalse(springboard.alerts.firstMatch.waitForExistence(timeout: 2), "a permission prompt before the person read why")
            next.tap()
        }
        let allow = ["Allow", "Permitir", "Allow While Using App", "Permitir al usar la app", "Keep Only While Using", "Mantener solo al usar la app"]
        for _ in 0..<12 where !app.textFields["pairLink"].waitForExistence(timeout: 3) {
            let alert = springboard.alerts.firstMatch
            if alert.exists, let button = alert.buttons.allElementsBoundByIndex.first(where: { allow.contains($0.label) }) { button.tap() }
        }

        let field = app.textFields["pairLink"]
        XCTAssertTrue(field.waitForExistence(timeout: 10), "pair screen not shown")
        field.tap()
        field.typeText(link)
        app.buttons["useLink"].tap()
        let pair = app.buttons["pair"]
        XCTAssertTrue(pair.waitForExistence(timeout: 5), "no confirmation before the secret is spent")
        pair.tap()

        let state = app.otherElements["state"].firstMatch
        XCTAssertTrue(state.waitForExistence(timeout: 20) || app.staticTexts["Avisos activos"].waitForExistence(timeout: 5), "home not shown")
        XCTAssertTrue(app.staticTexts["Avisos activos"].waitForExistence(timeout: 10), "not covered after pairing")
        attach(app, "paired-covered")
    }

    /// P0 of build 3: tapping a push banner crashed the app. A shell loop sends the server's test push
    /// (`xcrun simctl push`) while this waits on the home screen.
    func testTappingAPushOpensTheAlertScreen() throws {
        try testFirstRunToCoveredWithAPastedLink()
        let app = XCUIApplication()
        XCUIDevice.shared.press(.home)
        let banner = XCUIApplication(bundleIdentifier: "com.apple.springboard").otherElements["NotificationShortLookView"].firstMatch
        XCTAssertTrue(banner.waitForExistence(timeout: 90), "no banner: send the push while this runs")
        banner.tap()
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 10), "app did not come to the foreground (crash?)")
        XCTAssertTrue(app.buttons["close"].waitForExistence(timeout: 10), "alert screen not shown after the tap")
    }

    private func attach(_ app: XCUIApplication, _ name: String) {
        let shot = XCTAttachment(screenshot: app.screenshot())
        shot.name = name
        shot.lifetime = .keepAlways
        add(shot)
    }
}

/// The system accessibility audit on each sample screen: contrast, hit areas, labels, Dynamic Type clipping.
final class AccessibilityAuditUITests: XCTestCase {
    private func audit(_ state: String, wait identifier: String) throws {
        let app = XCUIApplication()
        app.launchArguments += ["-state", state, "-AppleLanguages", "(es)"]
        app.launch()
        XCTAssertTrue(app.descendants(matching: .any)[identifier].firstMatch.waitForExistence(timeout: 10), "\(state): \(identifier) missing")
        try app.performAccessibilityAudit()
    }

    func testCovered() throws { try audit("covered", wait: "state") }
    func testUnreachable() throws { try audit("unreachable", wait: "action") }
    func testTravelWarning() throws { try audit("travel-warning", wait: "travelWarningButton") }
    func testAlert() throws { try audit("alert", wait: "close") }
    func testLateAlert() throws { try audit("alert-late", wait: "lateTag") }
    func testDrillAlert() throws { try audit("alert-drill", wait: "drillBand") }
    func testTestAlert() throws { try audit("alert-test", wait: "testBand") }
    func testAfter() throws { try audit("after", wait: "afterTitle") }
    func testIntro() throws { try audit("intro", wait: "continue") }
    func testPair() throws { try audit("pair", wait: "pairLink") }
}
