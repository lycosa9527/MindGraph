window.__mgPwaInstallEarly = null
window.addEventListener('beforeinstallprompt', function (event) {
  event.preventDefault()
  window.__mgPwaInstallEarly = event
})
