package com.mindgraph.glasssheet

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Matrix
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import android.util.Size
import android.view.KeyEvent
import android.view.View
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import java.io.ByteArrayOutputStream
import java.util.concurrent.ExecutionException
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

class MainActivity : AppCompatActivity() {
    private lateinit var statusView: TextView
    private lateinit var lessonCard: LessonCard
    private lateinit var standbyView: TextView
    private lateinit var remotePanel: View
    private lateinit var remoteHint: TextView
    private lateinit var splash: View
    private lateinit var settingsPanel: View
    private lateinit var settingsHint: TextView
    private lateinit var slider: ModeSlider
    private lateinit var cameraExecutor: ExecutorService
    private lateinit var standby: StandbyStatus
    private lateinit var canvasRemote: CanvasRemote
    private lateinit var lesson: LessonPlay
    private lateinit var speaker: LessonVoice
    private lateinit var clock: HudClock
    private lateinit var intro: LaunchIntro
    private val nav = GlassNav()
    private val sheetArmed = AtomicBoolean(false)
    private val binding = AtomicBoolean(false)
    private var cameraProvider: ProcessCameraProvider? = null
    private var cameraOpen = false
    private var watchedToken = ""
    private val settingRows = linkedMapOf<GlassSetting, TextView>()
    private val cells = linkedMapOf<RemoteAction, TextView>()
    private val gate = SheetGate()
    private val uploader = SheetUploader()
    private val busy = AtomicBoolean(false)
    private val loggedFrame = AtomicBoolean(false)
    private val statusExecutor = Executors.newSingleThreadScheduledExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())
    private val lessonTap = LessonTap()
    private var shownSeq = 0
    private val holdHome = Runnable {
        if (lessonTap.hold()) finish()
    }

    private val cameraPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted && sheetArmed.get()) {
            startCamera()
        } else if (!granted) {
            cameraOpen = false
            show(getString(R.string.status_need_camera), sent = false)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        bindViews()
        findViewById<TextView>(R.id.splash_version).text = BuildConfig.VERSION_NAME
        standby = StandbyStatus(this, uploader)
        canvasRemote = CanvasRemote(uploader.endpoint())
        lesson = LessonPlay(uploader.endpoint())
        speaker = LessonVoice(this)
        cameraExecutor = Executors.newSingleThreadExecutor()
        clock = HudClock(findViewById(R.id.clock))
        intro = LaunchIntro(
            splash,
            findViewById(R.id.logo),
            findViewById(R.id.brand),
            findViewById(R.id.credit),
            findViewById(R.id.splash_lasers),
            getString(R.string.brand),
        )
        wireClicks()
        paintChrome()
        paintStandby(Link.CONNECTING)
        intro.play()
        clock.start()
        statusExecutor.scheduleWithFixedDelay(::refreshLink, 0, 5, TimeUnit.SECONDS)
        ensureCourseWatch()
    }

    override fun onDestroy() {
        mainHandler.removeCallbacks(holdHome)
        if (::intro.isInitialized) intro.finish()
        if (::lessonCard.isInitialized) lessonCard.clear()
        if (::clock.isInitialized) clock.stop()
        if (::speaker.isInitialized) speaker.stop()
        if (::lesson.isInitialized) lesson.stop()
        super.onDestroy()
        if (::cameraExecutor.isInitialized) cameraExecutor.shutdown()
        statusExecutor.shutdown()
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.keyCode == KeyEvent.KEYCODE_BACK && lessonCueOpen()) {
            if (event.action == KeyEvent.ACTION_DOWN && event.repeatCount == 0) finish()
            return true
        }
        val key = navKey(event.keyCode) ?: return super.dispatchKeyEvent(event)
        if (splash.visibility == View.VISIBLE) {
            if (event.action == KeyEvent.ACTION_DOWN && key == NavKey.CONFIRM) intro.finish()
            return true
        }
        if (key == NavKey.CONFIRM && lessonCueOpen()) return onLessonConfirm(event)
        if (event.action != KeyEvent.ACTION_DOWN) return super.dispatchKeyEvent(event)
        if (event.repeatCount > 0 && key == NavKey.CONFIRM) return true
        val insideSettings = !nav.onBar && nav.mode == GlassMode.SETTINGS
        val action = nav.onKey(key)
        if (insideSettings && key == NavKey.CONFIRM) applySetting(nav.setting)
        paintChrome()
        if (action != null) fire(action)
        return true
    }

    private fun bindViews() {
        statusView = findViewById(R.id.status)
        lessonCard = LessonCard(findViewById(R.id.lesson_card), findViewById(R.id.lesson_line))
        standbyView = findViewById(R.id.standby)
        remotePanel = findViewById(R.id.remote_panel)
        remoteHint = findViewById(R.id.remote_hint)
        splash = findViewById(R.id.splash)
        settingsPanel = findViewById(R.id.settings_panel)
        settingsHint = findViewById(R.id.settings_hint)
        slider = ModeSlider(
            findViewById(R.id.mode_slider),
            findViewById(R.id.mode_prev),
            findViewById(R.id.mode_current),
            findViewById(R.id.mode_icon),
            findViewById(R.id.mode_label),
            findViewById(R.id.mode_next),
        )
        settingRows[GlassSetting.BIND] = findViewById(R.id.setting_bind)
        settingRows[GlassSetting.UNBIND] = findViewById(R.id.setting_unbind)
        settingRows[GlassSetting.EXIT] = findViewById(R.id.setting_exit)
        cells[RemoteAction.PAN_UP] = findViewById(R.id.remote_up)
        cells[RemoteAction.PAN_LEFT] = findViewById(R.id.remote_left)
        cells[RemoteAction.FIT] = findViewById(R.id.remote_fit)
        cells[RemoteAction.PAN_RIGHT] = findViewById(R.id.remote_right)
        cells[RemoteAction.ZOOM_OUT] = findViewById(R.id.remote_zoom_out)
        cells[RemoteAction.PAN_DOWN] = findViewById(R.id.remote_down)
        cells[RemoteAction.ZOOM_IN] = findViewById(R.id.remote_zoom_in)
    }

    private fun wireClicks() {
        slider.wire(
            onSlide = { delta ->
                if (!nav.onBar) nav.showBar()
                nav.onKey(if (delta < 0) NavKey.LEFT else NavKey.RIGHT)
                paintChrome()
            },
            onConfirm = {
                if (nav.onBar) nav.onKey(NavKey.CONFIRM) else nav.showBar()
                paintChrome()
            },
        )
        for ((setting, view) in settingRows) {
            view.setOnClickListener {
                nav.focus(setting)
                applySetting(setting)
                paintChrome()
            }
        }
        for ((action, view) in cells) {
            view.setOnClickListener {
                nav.focus(action)
                paintChrome()
                fire(action)
            }
        }
    }

    private var chromeMode: GlassMode? = null

    private fun paintChrome() {
        val courseOn = nav.mode == GlassMode.COURSE
        val canvasOn = nav.mode == GlassMode.CANVAS
        val settingsOn = nav.mode == GlassMode.SETTINGS
        val arrived = nav.mode != chromeMode
        chromeMode = nav.mode
        if (arrived && courseOn && !lessonCard.isActive()) showIdle(R.string.status_wait_course)
        slider.render(nav.mode, nav.neighbor(-1), nav.neighbor(1), nav.onBar, nav.takeSlide())
        val lessonOn = courseOn && lessonCard.isActive()
        statusView.visibility = if (courseOn && !lessonOn) View.VISIBLE else View.GONE
        lessonCard.setSheetVisible(courseOn)
        remotePanel.visibility = if (canvasOn) View.VISIBLE else View.GONE
        settingsPanel.visibility = if (settingsOn) View.VISIBLE else View.GONE
        val onBindRow = settingsOn && !nav.onBar && nav.setting == GlassSetting.BIND
        if (!onBindRow) binding.set(false)
        sheetArmed.set(binding.get())
        syncCamera()
        val focusedSetting = if (settingsOn && !nav.onBar) nav.setting else null
        for ((setting, view) in settingRows) {
            view.setTextColor(if (setting == focusedSetting) WAITING_COLOR else DIM)
        }
        val focused = if (canvasOn && !nav.onBar) nav.pad.current() else null
        for ((action, view) in cells) {
            val on = action == focused
            view.setBackgroundResource(if (on) R.drawable.bg_remote_on else R.drawable.bg_remote_off)
            view.setTextColor(if (on) INK else WAITING_COLOR)
        }
    }

    private fun applySetting(setting: GlassSetting) {
        when (setting) {
            GlassSetting.BIND -> {
                binding.set(true)
                settingsHint.text = getString(R.string.setting_look)
            }
            GlassSetting.UNBIND -> {
                binding.set(false)
                standby.clearWearer()
                watchedToken = ""
                lesson.stop()
                settingsHint.text = getString(R.string.setting_cleared)
            }
            GlassSetting.EXIT -> finish()
        }
    }

    private fun fire(action: RemoteAction) {
        val needBind = getString(R.string.remote_need_bind)
        val failed = getString(R.string.remote_failed)
        remoteHint.text = cellLabel(action)
        val token = standby.wearerToken()
        statusExecutor.execute {
            val line = when (val ack = canvasRemote.send(token, action.wire)) {
                RemoteAck.NEED_BIND -> needBind
                RemoteAck.FAILED -> failed
                is RemoteAck.Sent -> ack.line
            }
            runOnUiThread { remoteHint.text = line }
        }
    }

    private fun cellLabel(action: RemoteAction): String = when (action) {
        RemoteAction.PAN_UP -> getString(R.string.remote_up)
        RemoteAction.PAN_DOWN -> getString(R.string.remote_down)
        RemoteAction.PAN_LEFT -> getString(R.string.remote_left)
        RemoteAction.PAN_RIGHT -> getString(R.string.remote_right)
        RemoteAction.ZOOM_IN -> getString(R.string.remote_zoom_in)
        RemoteAction.ZOOM_OUT -> getString(R.string.remote_zoom_out)
        RemoteAction.FIT -> getString(R.string.remote_fit)
    }

    private fun ensureCourseWatch() {
        if (!::lesson.isInitialized || !::standby.isInitialized || !::speaker.isInitialized) return
        val token = standby.wearerToken()
        if (token.isBlank() || token == watchedToken) return
        watchedToken = token
        lesson.watch(
            token,
            onFollow = { slide ->
                if (slide.seq == shownSeq) return@watch
                shownSeq = slide.seq
                runOnUiThread { showFollow(slide) }
            },
            onVoice = { audio ->
                if (audio.isEmpty()) return@watch
                runOnUiThread { speaker.playRecording("", audio) {} }
            },
        )
    }

    private fun showFollow(slide: FollowSlide) {
        if (!slide.active || slide.done || slide.line.isBlank()) {
            if (nav.mode == GlassMode.COURSE) showCourseNotice(slide)
            return
        }
        if (nav.mode != GlassMode.COURSE) nav.showCourse()
        paintChrome()
        showLesson(slide.line)
        speaker.playRecording(slide.line, slide.audio) { duration ->
            lessonCard.followVoice(duration)
        }
    }

    private fun refreshLink() {
        if (link != Link.CONNECTED) {
            runOnUiThread { paintStandby(Link.CONNECTING) }
        }
        val online = standby.online()
        runOnUiThread { paintStandby(if (online) Link.CONNECTED else Link.OFFLINE) }
    }

    private fun paintStandby(next: Link) {
        link = next
        standbyView.text = getString(
            when (next) {
                Link.CONNECTING -> R.string.status_connecting
                Link.CONNECTED -> R.string.status_connected
                Link.OFFLINE -> R.string.status_offline
            },
        )
    }

    private fun syncCamera() {
        if (!sheetArmed.get()) {
            cameraProvider?.unbindAll()
            cameraOpen = false
            return
        }
        if (cameraOpen) return
        val granted = ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) ==
            PackageManager.PERMISSION_GRANTED
        if (!granted) {
            cameraPermission.launch(Manifest.permission.CAMERA)
            return
        }
        startCamera()
    }

    private fun startCamera() {
        cameraOpen = true
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            val provider = try {
                future.get()
            } catch (error: ExecutionException) {
                Log.e(TAG, "camera provider failed", error)
                cameraOpen = false
                show(getString(R.string.status_no_camera), sent = false)
                return@addListener
            } catch (error: InterruptedException) {
                Thread.currentThread().interrupt()
                Log.e(TAG, "camera provider interrupted", error)
                cameraOpen = false
                show(getString(R.string.status_no_camera), sent = false)
                return@addListener
            }
            if (!sheetArmed.get()) {
                cameraOpen = false
                return@addListener
            }
            cameraProvider = provider
            bindCamera(provider)
        }, ContextCompat.getMainExecutor(this))
    }

    private fun bindCamera(provider: ProcessCameraProvider) {
        val selector = when {
            provider.hasCamera(CameraSelector.DEFAULT_BACK_CAMERA) -> CameraSelector.DEFAULT_BACK_CAMERA
            provider.hasCamera(CameraSelector.DEFAULT_FRONT_CAMERA) -> CameraSelector.DEFAULT_FRONT_CAMERA
            else -> {
                cameraOpen = false
                show(getString(R.string.status_no_camera), sent = false)
                return
            }
        }
        val analysis = ImageAnalysis.Builder()
            .setResolutionSelector(
                ResolutionSelector.Builder()
                    .setResolutionFilter { sizes, _ ->
                        val capped = sizes.filter { it.width <= SCAN_WIDTH && it.height <= SCAN_HEIGHT }
                        capped.ifEmpty { sizes }
                    }
                    .setResolutionStrategy(
                        ResolutionStrategy(
                            Size(SCAN_WIDTH, SCAN_HEIGHT),
                            ResolutionStrategy.FALLBACK_RULE_CLOSEST_LOWER_THEN_HIGHER,
                        ),
                    )
                    .build(),
            )
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
            .build()
        analysis.setAnalyzer(cameraExecutor, ::onFrame)
        try {
            provider.unbindAll()
            val camera = provider.bindToLifecycle(this, selector, analysis)
            cameraOpen = true
            camera.cameraInfo.cameraState.observe(this) { state ->
                val error = state.error
                if (error != null) {
                    Log.e(TAG, "camera error code=${error.code}")
                    show(getString(R.string.status_no_camera), sent = false)
                }
            }
        } catch (error: IllegalArgumentException) {
            Log.e(TAG, "camera bind failed", error)
            cameraOpen = false
            show(getString(R.string.status_no_camera), sent = false)
        }
    }

    private fun onFrame(image: ImageProxy) {
        if (!sheetArmed.get()) {
            image.close()
            return
        }
        if (loggedFrame.compareAndSet(false, true)) {
            Log.i(TAG, "analysis ${image.width}x${image.height} rot=${image.imageInfo.rotationDegrees}")
        }
        val sheetId = try {
            QrDecoder.read(image)
        } catch (error: RuntimeException) {
            Log.w(TAG, "qr read failed", error)
            null
        }
        if (!sheetArmed.get()) {
            image.close()
            return
        }
        if (sheetId == null || !gate.onFrame(sheetId, SystemClock.elapsedRealtime())) {
            image.close()
            return
        }
        if (!busy.compareAndSet(false, true)) {
            image.close()
            return
        }
        Log.i(TAG, "sheet $sheetId")
        val jpeg = try {
            jpegBytes(image)
        } catch (error: RuntimeException) {
            Log.e(TAG, "jpeg failed", error)
            image.close()
            busy.set(false)
            runOnUiThread { show(getString(R.string.status_failed), sent = false) }
            return
        }
        image.close()
        runOnUiThread { show(getString(R.string.status_shooting), sent = false) }
        val line = uploader.send(sheetId, jpeg)
        val sent = !line.startsWith("发送失败")
        if (uploader.isDeviceBound(line)) {
            standby.rememberWearer(sheetId)
            runOnUiThread { ensureCourseWatch() }
        }
        if (!sent) gate.forget()
        runOnUiThread {
            show(line, sent)
            if (nav.mode == GlassMode.SETTINGS) {
                settingsHint.text = if (uploader.isDeviceBound(line)) {
                    getString(R.string.setting_bound)
                } else {
                    line
                }
            }
            paintStandby(if (sent) Link.CONNECTED else Link.OFFLINE)
        }
        busy.set(false)
    }

    private fun lessonCueOpen(): Boolean = nav.mode == GlassMode.COURSE

    private fun onLessonConfirm(event: KeyEvent): Boolean {
        if (event.repeatCount > 0) return true
        when (event.action) {
            KeyEvent.ACTION_DOWN -> {
                lessonTap.press()
                mainHandler.removeCallbacks(holdHome)
                mainHandler.postDelayed(holdHome, LESSON_HOLD_MS)
            }
            KeyEvent.ACTION_UP -> {
                mainHandler.removeCallbacks(holdHome)
                if (lessonTap.release()) advanceLesson()
            }
        }
        return true
    }

    private fun advanceLesson() {
        if (!busy.compareAndSet(false, true)) return
        val token = standby.wearerToken()
        statusExecutor.execute {
            val ack = lesson.askNext(token)
            runOnUiThread {
                when (ack) {
                    NextAck.Accepted -> Unit
                    NextAck.NeedBind -> show(getString(R.string.status_course_bind), sent = false)
                    NextAck.Idle -> show(getString(R.string.status_wait_course), sent = false)
                    NextAck.Over -> show(getString(R.string.status_course_over), sent = false)
                    NextAck.Failed -> show(getString(R.string.status_course_failed), sent = false)
                }
            }
            busy.set(false)
        }
    }

    private fun showCourseNotice(slide: FollowSlide) {
        val message = when {
            slide.done -> R.string.status_course_over
            slide.active -> R.string.status_course_started
            else -> R.string.status_wait_course
        }
        show(getString(message), sent = false)
    }

    private fun showLesson(text: String) {
        statusView.visibility = View.GONE
        lessonCard.play(text)
    }

    private fun showIdle(message: Int) {
        statusView.text = getString(message)
        statusView.setTextColor(WAITING_COLOR)
    }

    private fun show(text: String, sent: Boolean) {
        lessonCard.clear()
        statusView.text = text
        statusView.setTextColor(if (sent) SENT_COLOR else WAITING_COLOR)
        val reading = nav.mode == GlassMode.COURSE
        if (reading) statusView.visibility = View.VISIBLE
    }

    private var link = Link.CONNECTING

    private enum class Link {
        CONNECTING,
        CONNECTED,
        OFFLINE,
    }

    private companion object {
        const val TAG = "MindGlass"
        const val SENT_COLOR = 0xFF3DDC84.toInt()
        const val WAITING_COLOR = 0xFFFFFFFF.toInt()
        const val INK = 0xFF000000.toInt()
        const val DIM = 0x66FFFFFF.toInt()
        const val SCAN_WIDTH = 1920
        const val SCAN_HEIGHT = 1440
        const val SHEET_UPRIGHT_DEGREES = -90f
        const val LESSON_HOLD_MS = 500L

        fun navKey(code: Int): NavKey? = when (code) {
            KeyEvent.KEYCODE_DPAD_LEFT -> NavKey.LEFT
            KeyEvent.KEYCODE_DPAD_RIGHT -> NavKey.RIGHT
            KeyEvent.KEYCODE_DPAD_UP -> NavKey.UP
            KeyEvent.KEYCODE_DPAD_DOWN -> NavKey.DOWN
            KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_NUMPAD_ENTER -> NavKey.CONFIRM
            else -> null
        }

        fun jpegBytes(image: ImageProxy): ByteArray {
            val bitmap = uprightSheet(image.toBitmap())
            val stream = ByteArrayOutputStream()
            bitmap.compress(Bitmap.CompressFormat.JPEG, 80, stream)
            bitmap.recycle()
            return stream.toByteArray()
        }

        fun uprightSheet(source: Bitmap): Bitmap {
            val matrix = Matrix()
            matrix.postRotate(SHEET_UPRIGHT_DEGREES)
            val rotated = Bitmap.createBitmap(source, 0, 0, source.width, source.height, matrix, true)
            if (rotated !== source) {
                source.recycle()
            }
            return rotated
        }
    }
}
