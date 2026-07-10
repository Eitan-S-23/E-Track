import UIKit
import Flutter

@UIApplicationMain
@objc class AppDelegate: FlutterAppDelegate {
  private let deepLinkChannelName = "trace/deep_link"
  private var deepLinkChannel: FlutterMethodChannel?
  private var initialLink: String?

  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    if let url = launchOptions?[.url] as? URL {
      initialLink = url.absoluteString
    }

    GeneratedPluginRegistrant.register(with: self)

    if let controller = window?.rootViewController as? FlutterViewController {
      deepLinkChannel = FlutterMethodChannel(
        name: deepLinkChannelName,
        binaryMessenger: controller.binaryMessenger
      )
      deepLinkChannel?.setMethodCallHandler { [weak self] call, result in
        if call.method == "getInitialLink" {
          result(self?.initialLink)
        } else {
          result(FlutterMethodNotImplemented)
        }
      }
    }

    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  override func application(
    _ app: UIApplication,
    open url: URL,
    options: [UIApplication.OpenURLOptionsKey: Any] = [:]
  ) -> Bool {
    if url.scheme == "trace" {
      handleDeepLink(url)
      return true
    }

    return super.application(app, open: url, options: options)
  }

  private func handleDeepLink(_ url: URL) {
    let link = url.absoluteString
    initialLink = link
    deepLinkChannel?.invokeMethod("onDeepLink", arguments: link)
  }
}
