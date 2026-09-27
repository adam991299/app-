import XCTest

final class AppLaunchUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    func testLaunchShowsAllTabs() throws {
        let app = XCUIApplication()
        app.launchArguments += ["-ui-testing", "-AppleLanguages", "(sv)", "-AppleLocale", "sv_SE"]
        app.launch()

        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 10))
        for title in ["Idag", "Tävlingar", "Profil"] {
            XCTAssertTrue(tabBar.buttons[title].exists, "Fliken \(title) saknas")
        }

        tabBar.buttons["Tävlingar"].tap()
        XCTAssertTrue(app.navigationBars["Tävlingar"].waitForExistence(timeout: 5))

        tabBar.buttons["Profil"].tap()
        XCTAssertTrue(app.navigationBars["Profil"].waitForExistence(timeout: 5))
    }
}
