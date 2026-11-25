// Play a WAV and say when its first sample is heard.
//
// afplay starts when it starts: tens of ms on the speakers, most of a second on
// Bluetooth headphones, and nothing says which. This plays the file from a moment
// fixed ahead of time (LEAD after the output is running, so a Bluetooth link is up
// by then) and prints one line, "heard <ns>": how long from now until the first
// sample leaves the headphones, the output's own delay included. Exits when the
// last sample has been heard, 1 if the output goes away meanwhile.

import AVFoundation

let LEAD = 1.0      // seconds of silence into a running output before the file

guard CommandLine.arguments.count == 2,
      let file = try? AVAudioFile(forReading: URL(fileURLWithPath: CommandLine.arguments[1])) else {
    FileHandle.standardError.write("usage: player file.wav\n".data(using: .utf8)!)
    exit(2)
}
let engine = AVAudioEngine()
let node = AVAudioPlayerNode()
engine.attach(node)
engine.connect(node, to: engine.mainMixerNode, format: file.processingFormat)
do { try engine.start() } catch {
    FileHandle.standardError.write("player: \(error.localizedDescription)\n".data(using: .utf8)!)
    exit(2)
}
NotificationCenter.default.addObserver(forName: .AVAudioEngineConfigurationChange, object: engine, queue: nil) { _ in exit(1) }

node.scheduleFile(file, at: nil, completionCallbackType: .dataPlayedBack) { _ in exit(0) }
let delay = engine.outputNode.presentationLatency       // from the output's buffer to the ear, as the device reports it
let start = mach_absolute_time() + AVAudioTime.hostTime(forSeconds: LEAD)
node.play(at: AVAudioTime(hostTime: start))
let heard = AVAudioTime.seconds(forHostTime: start - mach_absolute_time()) + delay
print("heard \(Int(heard * 1e9))")
fflush(stdout)
RunLoop.main.run()
