import AppKit
import Darwin
import SQLite3

struct LauncherError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

final class ServerController {
    let data: URL
    let logs: URL
    private(set) var process: Process?
    private var lock: Int32 = -1
    private var output: FileHandle?
    var onExit: ((Int32) -> Void)?

    init() {
        let home = FileManager.default.homeDirectoryForCurrentUser
        if let override = ProcessInfo.processInfo.environment["KAPOWARR_DATA_DIR"] {
            data = URL(fileURLWithPath: override, isDirectory: true)
            logs = data.appendingPathComponent("logs", isDirectory: true)
        } else {
            data = home.appendingPathComponent("Library/Application Support/Kapowarr", isDirectory: true)
            logs = home.appendingPathComponent("Library/Logs/Kapowarr", isDirectory: true)
        }
    }

    func serverURL() throws -> URL {
        let database = data.appendingPathComponent("Kapowarr.db")
        var port = "5656"
        var base = ""
        if FileManager.default.fileExists(atPath: database.path) {
            var db: OpaquePointer?
            guard sqlite3_open_v2(database.path, &db, SQLITE_OPEN_READONLY, nil) == SQLITE_OK else {
                if let db { sqlite3_close(db) }
                throw LauncherError(message: "Cannot read the Kapowarr database at \(database.path).")
            }
            defer { sqlite3_close(db) }
            sqlite3_busy_timeout(db, 2000)
            var statement: OpaquePointer?
            let query = "SELECT key, value FROM config WHERE key IN ('port', 'url_base')"
            if sqlite3_prepare_v2(db, query, -1, &statement, nil) == SQLITE_OK {
                defer { sqlite3_finalize(statement) }
                while sqlite3_step(statement) == SQLITE_ROW {
                    guard let keyText = sqlite3_column_text(statement, 0),
                          let valueText = sqlite3_column_text(statement, 1) else { continue }
                    let key = String(cString: keyText)
                    let value = String(cString: valueText)
                    if key == "port" { port = value }
                    if key == "url_base" { base = value }
                }
            }
        }
        guard let number = Int(port), (1...65535).contains(number),
              let url = URL(string: "http://127.0.0.1:\(number)\(base)/") else {
            throw LauncherError(message: "Kapowarr's saved port or URL base is invalid.")
        }
        return url
    }

    func start() throws {
        let fm = FileManager.default
        try fm.createDirectory(at: data, withIntermediateDirectories: true)
        try fm.createDirectory(at: logs, withIntermediateDirectories: true)
        lock = Darwin.open(data.appendingPathComponent("launcher.lock").path, O_CREAT | O_RDWR, 0o600)
        guard lock >= 0, flock(lock, LOCK_EX | LOCK_NB) == 0 else {
            throw LauncherError(message: "Kapowarr is already running. Use its menu-bar icon to open it.")
        }
        // Do not pass the lock into the backend or conversion processes.
        _ = fcntl(lock, F_SETFD, FD_CLOEXEC)
        let url = try serverURL()
        let socket = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard socket >= 0 else { throw LauncherError(message: "Cannot check Kapowarr's port.") }
        var reuse: Int32 = 1
        setsockopt(socket, SOL_SOCKET, SO_REUSEADDR, &reuse, socklen_t(MemoryLayout<Int32>.size))
        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = in_port_t(url.port!).bigEndian
        address.sin_addr.s_addr = inet_addr("127.0.0.1")
        let available = withUnsafePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.bind(socket, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) == 0
            }
        }
        Darwin.close(socket)
        guard available else {
            throw LauncherError(message: "Port \(url.port!) is already in use. Quit the other Kapowarr instance or service, then open this app again.")
        }
        guard let resources = Bundle.main.resourceURL else {
            throw LauncherError(message: "Kapowarr's bundled server is missing. Reinstall the app.")
        }
        let server = Process()
        server.executableURL = resources.appendingPathComponent("server/kapowarr-server")
        server.currentDirectoryURL = data
        server.arguments = ["-d", data.path, "-l", logs.path, "-o", "127.0.0.1"]
        if !fm.fileExists(atPath: data.appendingPathComponent("Kapowarr.db").path) {
            let downloads = data.appendingPathComponent("temp_downloads", isDirectory: true)
            try fm.createDirectory(at: downloads, withIntermediateDirectories: true)
            server.arguments! += ["-t", downloads.path]
        }
        var environment = ProcessInfo.processInfo.environment
        environment.removeValue(forKey: "PYTHONHOME")
        environment.removeValue(forKey: "PYTHONPATH")
        environment.removeValue(forKey: "KAPOWARR_RUN_MAIN")
        environment.removeValue(forKey: "KAPOWARR_START_TYPE")
        environment["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        environment["PYTHONUNBUFFERED"] = "1"
        server.environment = environment
        let log = logs.appendingPathComponent("launcher.log")
        if !fm.fileExists(atPath: log.path) { fm.createFile(atPath: log.path, contents: nil) }
        let output = try FileHandle(forWritingTo: log)
        try output.seekToEnd()
        self.output = output
        server.standardOutput = output
        server.standardError = output
        server.terminationHandler = { [weak self] process in
            DispatchQueue.main.async { self?.onExit?(process.terminationStatus) }
        }
        try server.run()
        process = server
    }

    func stop(_ completion: @escaping () -> Void) {
        guard let process, process.isRunning else {
            DispatchQueue.main.async { completion() }
            return
        }
        process.terminate()
        DispatchQueue.global().async {
            let deadline = Date().addingTimeInterval(30)
            while process.isRunning && Date() < deadline { Thread.sleep(forTimeInterval: 0.1) }
            if process.isRunning {
                // The bundled entry point puts the server and its workers in
                // their own group, so a stuck child cannot outlive Quit.
                Darwin.kill(-process.processIdentifier, SIGKILL)
                Darwin.kill(process.processIdentifier, SIGKILL)
            }
            process.waitUntilExit()
            DispatchQueue.main.async { completion() }
        }
    }

    deinit {
        if lock >= 0 { Darwin.close(lock) }
        try? output?.close()
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    let server = ServerController()
    var item: NSStatusItem!
    let status = NSMenuItem(title: "Starting Kapowarr…", action: nil, keyEquivalent: "")
    var timer: Timer?
    var starting = true
    var stopping = false
    var checking = false
    var deadline = Date().addingTimeInterval(120)

    func applicationDidFinishLaunching(_ notification: Notification) {
        item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        item.button?.image = NSImage(systemSymbolName: "books.vertical", accessibilityDescription: "Kapowarr")
        let menu = NSMenu()
        menu.addItem(status)
        menu.addItem(.separator())
        menu.addItem(withTitle: "Open Kapowarr", action: #selector(openKapowarr), keyEquivalent: "o").target = self
        menu.addItem(withTitle: "View Logs", action: #selector(viewLogs), keyEquivalent: "l").target = self
        menu.addItem(withTitle: "Download Updates…", action: #selector(downloadUpdates), keyEquivalent: "").target = self
        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit Kapowarr", action: #selector(quit), keyEquivalent: "q").target = self
        item.menu = menu
        server.onExit = { [weak self] code in
            guard let self, !self.stopping else { return }
            if code != 0 { self.showError("Kapowarr stopped unexpectedly. Open View Logs for details.") }
            NSApp.terminate(nil)
        }
        do {
            try server.start()
            timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.checkServer() }
            checkServer()
        } catch {
            showError(error.localizedDescription)
            NSApp.terminate(nil)
        }
    }

    func checkServer() {
        guard !checking, !stopping, let url = try? server.serverURL() else { return }
        checking = true
        var request = URLRequest(url: url)
        request.timeoutInterval = 2
        URLSession.shared.dataTask(with: request) { [weak self] _, response, _ in
            DispatchQueue.main.async {
                guard let self, !self.stopping else { return }
                self.checking = false
                if let response = response as? HTTPURLResponse, response.statusCode == 200 {
                    self.status.title = "Kapowarr is running"
                    if self.starting {
                        self.starting = false
                        NSWorkspace.shared.open(url)
                    }
                } else if self.starting && Date() > self.deadline {
                    self.starting = false
                    self.showError("Kapowarr is taking longer than expected to start. View Logs has the startup details. The app will keep running.")
                } else if !self.starting {
                    self.status.title = "Kapowarr is restarting…"
                }
            }
        }.resume()
    }

    @objc func openKapowarr() {
        if let url = try? server.serverURL() { NSWorkspace.shared.open(url) }
    }
    @objc func viewLogs() { NSWorkspace.shared.open(server.logs) }
    @objc func downloadUpdates() {
        NSWorkspace.shared.open(URL(string: "https://github.com/llithium/Kapowarr/releases")!)
    }
    @objc func quit() { NSApp.terminate(nil) }

    func showError(_ message: String) {
        NSApp.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.messageText = "Kapowarr"
        alert.informativeText = message
        alert.addButton(withTitle: "OK")
        alert.addButton(withTitle: "View Logs")
        if alert.runModal() == .alertSecondButtonReturn { viewLogs() }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        openKapowarr()
        return false
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard !stopping else { return .terminateLater }
        stopping = true
        timer?.invalidate()
        status.title = "Stopping Kapowarr…"
        server.stop { sender.reply(toApplicationShouldTerminate: true) }
        return .terminateLater
    }
}

// Exercise the same supervisor without opening a browser or a menu during CI.
if CommandLine.arguments.dropFirst().first == "--smoke-test" {
    let controller = ServerController()
    do {
        try controller.start()
        print("SERVER_PID=\(controller.process!.processIdentifier)")
        fflush(stdout)
        let seconds = Double(CommandLine.arguments.last ?? "") ?? 15
        RunLoop.current.run(until: Date().addingTimeInterval(seconds))
        var stopped = false
        controller.stop { stopped = true }
        while !stopped { RunLoop.current.run(until: Date().addingTimeInterval(0.1)) }
        print("Server stopped.")
    } catch {
        fputs("\(error.localizedDescription)\n", stderr)
        exit(1)
    }
} else {
    let app = NSApplication.shared
    let delegate = AppDelegate()
    app.setActivationPolicy(.accessory)
    app.delegate = delegate
    app.run()
}
