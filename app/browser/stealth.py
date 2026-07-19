"""Scripts d'init stealth — patches anti-détection pour Playwright.

Ces scripts sont injectés via `context.add_init_script()` avant le chargement
de toute page. Ils patchent les principaux vecteurs de détection d'automation
détectés par DataDome, Cloudflare, PerimeterX, etc.

Sources : recherche publique sur les fingerprint anti-bot (2024-2025).
"""

# Le script JS suivant est exécuté dans chaque page/frame avant tout autre code.
# Il supprime les signaux d'automation les plus courants.

STEALTH_INIT_SCRIPT = r"""
(() => {
    'use strict';

    // --- navigator.webdriver → undefined ---
    try {
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true,
        });
    } catch (e) {}

    // --- window.chrome (manquant en headless) ---
    if (!window.chrome) {
        window.chrome = {
            runtime: {},
            loadTimes: () => {},
            csi: () => {},
            app: {},
        };
    }

    // --- navigator.plugins (vide en headless) ---
    try {
        const fakePlugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: '' },
            { name: 'Native Client', filename: 'internal-pdf-viewer', description: '' },
        ];
        Object.defineProperty(navigator, 'plugins', {
            get: () => fakePlugins,
            configurable: true,
        });
    } catch (e) {}

    // --- navigator.mimeTypes ---
    try {
        const fakeMimeTypes = [
            { type: 'application/pdf', suffixes: 'pdf', description: '' },
            { type: 'text/pdf', suffixes: 'pdf', description: '' },
        ];
        Object.defineProperty(navigator, 'mimeTypes', {
            get: () => fakeMimeTypes,
            configurable: true,
        });
    } catch (e) {}

    // --- navigator.languages ---
    try {
        Object.defineProperty(navigator, 'languages', {
            get: () => ['fr-FR', 'fr', 'en-US', 'en'],
            configurable: true,
        });
    } catch (e) {}

    // --- navigator.permissions.query (patch l'incohérence notifications) ---
    try {
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => {
            if (parameters.name === 'notifications') {
                return Promise.resolve({ state: Notification.permission, onchange: null });
            }
            return originalQuery.call(window.navigator.permissions, parameters);
        };
    } catch (e) {}

    // --- navigator.hardwareConcurrency ---
    try {
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8,
            configurable: true,
        });
    } catch (e) {}

    // --- navigator.deviceMemory ---
    try {
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8,
            configurable: true,
        });
    } catch (e) {}

    // --- navigator.connection ---
    try {
        if (!navigator.connection) {
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                    saveData: false,
                }),
                configurable: true,
            });
        }
    } catch (e) {}

    // --- WebGL Vendor & Renderer (évitait "Google SwiftShader") ---
    try {
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function (parameter) {
            // UNMASKED_VENDOR_WEBGL
            if (parameter === 37445) return 'Intel Inc.';
            // UNMASKED_RENDERER_WEBGL
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return getParameter.call(this, parameter);
        };
    } catch (e) {}

    // --- WebGL2 ---
    try {
        if (typeof WebGL2RenderingContext !== 'undefined') {
            const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
            WebGL2RenderingContext.prototype.getParameter = function (parameter) {
                if (parameter === 37445) return 'Intel Inc.';
                if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                return getParameter2.call(this, parameter);
            };
        }
    } catch (e) {}

    // --- mediaDevices (évitait le fingerprint vide) ---
    try {
        if (!navigator.mediaDevices) {
            Object.defineProperty(navigator, 'mediaDevices', {
                get: () => ({
                    enumerateDevices: () => Promise.resolve([
                        { kind: 'audioinput', deviceId: 'default', label: '', groupId: 'default' },
                        { kind: 'audiooutput', deviceId: 'default', label: '', groupId: 'default' },
                        { kind: 'videoinput', deviceId: 'default', label: '', groupId: 'default' },
                    ]),
                    getUserMedia: () => Promise.reject(new Error('Permission denied')),
                }),
                configurable: true,
            });
        }
    } catch (e) {}

    // --- iframe.contentWindow (clobbering anti-detection) ---
    try {
        const originalContentWindow = HTMLIFrameElement.prototype.__lookupGetter__('contentWindow');
        if (originalContentWindow) {
            Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
                get: function () {
                    const cw = originalContentWindow.call(this);
                    if (cw) {
                        try {
                            // ne rien casser, juste s'assurer que l'iframe n'expose pas webdriver
                            Object.defineProperty(cw.navigator, 'webdriver', {
                                get: () => undefined,
                                configurable: true,
                            });
                        } catch (e) {}
                    }
                    return cw;
                },
                configurable: true,
            });
        }
    } catch (e) {}

    // --- CDP detection: masquer les artefacts Chrome DevTools Protocol ---
    try {
        // supprimer les propriétés exposées par --enable-automation
        delete window.cdc_adoQpoasnFa9IF7T5nQ6t2jFgWjV1zVQ7IQJbQ1o;
        delete window.cdc_dialog;
        // masquer les variables injectées par CDP
        for (const key of Object.keys(window)) {
            if (key.startsWith('cdc_') || key.startsWith('cdc$')) {
                delete window[key];
            }
        }
    } catch (e) {}

    // --- toString spoofing pour les méthodes patchées ---
    try {
        const nativeToString = Function.prototype.toString;
        const patchedMethods = [
            navigator.permissions.query,
            WebGLRenderingContext.prototype.getParameter,
        ];
        if (typeof WebGL2RenderingContext !== 'undefined') {
            patchedMethods.push(WebGL2RenderingContext.prototype.getParameter);
        }
        for (const method of patchedMethods) {
            if (method && method.toString) {
                method.toString = () => 'function ' + (method.name || '') + '() { [native code] }';
            }
        }
    } catch (e) {}
})();
"""
