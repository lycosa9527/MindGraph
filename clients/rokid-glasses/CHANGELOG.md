# MindGlass

Version numbers come from [`version.properties`](version.properties). `VERSION_CODE` is what Android uses to accept an update. `VERSION_NAME` is the small number beside the clock.

## 0.2.21

- Mind Platform types in over laser streaks and sparks.

## 0.2.20

- The course screen says the teacher has not started yet, that class has started and to wait, or that this is the last slide.

## 0.2.19

- The spoken line types a little ahead of the recording, instead of racing through on a fixed timer.

## 0.2.18

- The glasses hold one course stream. A new slide or recording arrives as an event, and the camera opens only while binding.

## 0.2.17

- A follow-up with no new recording leaves the voiceover playing through the last sentence.

## 0.2.16

- The glasses open ready for the course. Once they are connected, the teacher's course plays without choosing a mode. The learning-sheet mode is gone.

## 0.2.15

- A course starts from the computer. The glasses follow that slide, and a tap asks the computer to move with them.

## 0.2.14

- The recording made for a slide plays on the glasses. The glasses read the line aloud only when that recording is missing.

## 0.2.13

- A slide's saved voiceover plays on the glasses. A line with no recording is read aloud instead.

## 0.2.12

- 课程 sits beside 学习单. Its screen says to look at the MindCourse QR code. A course code is read only from that mode.

## 0.2.11

- A course line appears in a green box. The cursor blinks, then the line types in.

## 0.2.10

- A tap during a course asks for the next step when the slide still has one, and the next slide when it does not.

## 0.2.9

- During a course slide, a tap asks the computer for the next slide. Holding the tap leaves back to the glasses home.

## 0.2.8

- A course slide code shows that slide's line and reads it aloud. Tap continues to the next slide.

## 0.2.7

- The main choice is one sliding name. Slide to the app, then tap to open it. Neighbors stay dim at the sides so more apps can be added later.

## 0.2.6

- A failed sheet photo can be taken again without looking away. The camera no longer clears that result back to the waiting line.

## 0.2.5

- The activity uses the glasses' landscape panel, so the portrait letterbox bars on both sides are gone.
- Launch is larger. The version sits at the bottom right of that screen only.
- 设置 sits beside 画布. It can bind, unbind, or leave back to the glasses home.

## 0.2.4

- Launch stays on a plain black field. The underline is gone. "built by MTEL" fades in under Mind Platform when the M gives way to the type effect.

## 0.2.3

- The corner line is only the link: 连接中, 已连接, or 离线. The address stays in the request and is not drawn.

## 0.2.2

- Local mode calls this computer's LAN address. `127.0.0.1` is the glasses themselves, so a sheet photo never reached the dev server. The install script writes the Wi-Fi address into `local-endpoint.properties`, and that host is what the corner line shows.

## 0.2.1

- The clock, version, and link state share one row. The host address is no longer drawn there, so it no longer runs into the time.
- The sheet line and the canvas pad sit in the band between that row and the bottom segment.

## 0.2.0

- The app is MindGlass. Launch shows the M mark, lets it expand, then types Mind Platform.
- The clock sits at the top left. The version name sits under it.
- The bottom segment switches between 学习单 and 画布.
- 学习单 keeps the sheet camera. 画布 is a remote for the open diagram: pan, zoom, and fit. It sends only after these glasses have photographed that account's bind QR.
- Install with [`install-on-glasses.sh`](install-on-glasses.sh).

## 0.1.0

- The app was labeled 学习单. It watched for an `mg://sheet/` QR, took the photo, and uploaded it.
- The waiting screen showed where the upload goes, whether that host answers, and whether a bind photo had already succeeded.
