"""Scripts d'init stealth — patches anti-détection avancés pour Playwright.

Ces scripts sont injectés via `context.add_init_script()` avant le chargement
de toute page. Ils patchent les principaux vecteurs de détection d'automation
détectés par DataDome, Cloudflare, PerimeterX, etc.

Version 2.0 — juillet 2026: patches complets (platform, UA hints, etc.)
"""

STEALTH_INIT_SCRIPT = r"""
(() => {
    'use strict';

    // =========================================================
    // 1. navigator.webdriver → undefined (critical for DataDome)
    // =========================================================
    try {
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true,
        });
    } catch (e) {}

    // Also delete it from the prototype
    try {
        delete Object.getPrototypeOf(navigator).webdriver;
    } catch (e) {}

    // =========================================================
    // 2. window.chrome (missing in headless/automation)
    // =========================================================
    if (!window.chrome) {
        window.chrome = {
            runtime: {
                onConnect: undefined,
                onMessage: undefined,
                connect: () => {},
                sendMessage: () => {},
            },
            loadTimes: () => ({
                requestTime: Date.now() / 1000 - 1,
                startLoad: 3,
                commitLoad: 3,
                finishDocumentLoad: 3,
                finishLoad: 3,
                firstPaint: 3,
                firstPaintAfterLoad: 3,
                navigationType: "Other",
                wasFetchedViaSpdy: true,
                wasNpnNegotiated: true,
                npnNegotiatedProtocol: "h2",
                wasAlternateProtocolAvailable: false,
                connectionInfo: "h2",
            }),
            csi: () => ({
                startE: Date.now() - 1000,
                onloadT: Date.now(),
                pageT: 1000,
                tran: 15,
            }),
            app: {
                isInstalled: false,
                InstallState: { DISABLED: "disabled", INSTALLED: "installed", NOT_INSTALLED: "not_installed" },
                RunningState: { CANNOT_RUN: "cannot_run", READY_TO_RUN: "ready_to_run", RUNNING: "running" },
                getDetails: () => {},
                getIsInstalled: () => false,
            },
        };
    }

    // =========================================================
    // 3. navigator.platform, navigator.oscpu, navigator.vendor
    //    Consistent Windows fingerprint (must match UA)
    // =========================================================
    try {
        Object.defineProperty(navigator, 'platform', {
            get: () => 'Win32',
            configurable: true,
        });
    } catch (e) {}

    try {
        Object.defineProperty(navigator, 'oscpu', {
            get: () => 'Windows NT 10.0; Win64; x64',
            configurable: true,
        });
    } catch (e) {}

    try {
        Object.defineProperty(navigator, 'vendor', {
            get: () => 'Google Inc.',
            configurable: true,
        });
    } catch (e) {}

    try {
        Object.defineProperty(navigator, 'vendorSub', {
            get: () => '',
            configurable: true,
        });
    } catch (e) {}

    try {
        Object.defineProperty(navigator, 'product', {
            get: () => 'Gecko',
            configurable: true,
        });
    } catch (e) {}

    try {
        Object.defineProperty(navigator, 'productSub', {
            get: () => '20030107',
            configurable: true,
        });
    } catch (e) {}

    try {
        Object.defineProperty(navigator, 'appName', {
            get: () => 'Netscape',
            configurable: true,
        });
    } catch (e) {}

    try {
        Object.defineProperty(navigator, 'appCodeName', {
            get: () => 'Mozilla',
            configurable: true,
        });
    } catch (e) {}

    // =========================================================
    // 4. navigator.plugins & mimeTypes (empty in headless)
    // =========================================================
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

    // =========================================================
    // 5. navigator.languages
    // =========================================================
    try {
        Object.defineProperty(navigator, 'languages', {
            get: () => ['fr-FR', 'fr', 'en-US', 'en'],
            configurable: true,
        });
    } catch (e) {}

    // =========================================================
    // 6. navigator.permissions.query (fix notifications inconsistency)
    // =========================================================
    try {
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => {
            if (parameters.name === 'notifications') {
                return Promise.resolve({ state: Notification.permission, onchange: null });
            }
            return originalQuery.call(window.navigator.permissions, parameters);
        };
    } catch (e) {}

    // =========================================================
    // 7. navigator.hardwareConcurrency & deviceMemory
    // =========================================================
    try {
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8,
            configurable: true,
        });
    } catch (e) {}

    try {
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8,
            configurable: true,
        });
    } catch (e) {}

    // =========================================================
    // 8. navigator.connection
    // =========================================================
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

    // =========================================================
    // 9. navigator.maxTouchPoints (desktop = 0)
    // =========================================================
    try {
        Object.defineProperty(navigator, 'maxTouchPoints', {
            get: () => 0,
            configurable: true,
        });
    } catch (e) {}

    // =========================================================
    // 10. navigator.doNotTrack
    // =========================================================
    try {
        Object.defineProperty(navigator, 'doNotTrack', {
            get: () => null,
            configurable: true,
        });
    } catch (e) {}

    // =========================================================
    // 11. navigator.cookieEnabled = true
    // =========================================================
    try {
        Object.defineProperty(navigator, 'cookieEnabled', {
            get: () => true,
            configurable: true,
        });
    } catch (e) {}

    // =========================================================
    // 12. navigator.pdfViewerEnabled = true (Chrome 100+)
    // =========================================================
    try {
        Object.defineProperty(navigator, 'pdfViewerEnabled', {
            get: () => true,
            configurable: true,
        });
    } catch (e) {}

    // =========================================================
    // 13. WebGL Vendor & Renderer (avoid "Google SwiftShader")
    // =========================================================
    try {
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function (parameter) {
            if (parameter === 37445) return 'Intel Inc.';        // UNMASKED_VENDOR_WEBGL
            if (parameter === 37446) return 'Intel Iris OpenGL Engine'; // UNMASKED_RENDERER_WEBGL
            return getParameter.call(this, parameter);
        };
    } catch (e) {}

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

    // =========================================================
    // 14. WebGL getExtension — spoof WEBGL_debug_renderer_info
    // =========================================================
    try {
        const origGetExtension = WebGLRenderingContext.prototype.getExtension;
        WebGLRenderingContext.prototype.getExtension = function(name) {
            if (name === 'WEBGL_debug_renderer_info') {
                return {
                    UNMASKED_VENDOR_WEBGL: 37445,
                    UNMASKED_RENDERER_WEBGL: 37446,
                };
            }
            return origGetExtension.call(this, name);
        };
    } catch (e) {}

    // =========================================================
    // 15. mediaDevices (avoid empty fingerprint)
    // =========================================================
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

    // =========================================================
    // 16. iframe.contentWindow — ensure no webdriver leaks through iframes
    // =========================================================
    try {
        const originalContentWindow = HTMLIFrameElement.prototype.__lookupGetter__('contentWindow');
        if (originalContentWindow) {
            Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
                get: function () {
                    const cw = originalContentWindow.call(this);
                    if (cw) {
                        try {
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

    // =========================================================
    // 17. CDP detection — hide Chrome DevTools Protocol artifacts
    // =========================================================
    try {
        delete window.cdc_adoQpoasnFa9IF7T5nQ6t2jFgWjV1zVQ7IQJbQ1o;
        delete window.cdc_dialog;
        for (const key of Object.keys(window)) {
            if (key.startsWith('cdc_') || key.startsWith('cdc$')) {
                delete window[key];
            }
        }
    } catch (e) {}

    // =========================================================
    // 18. Notification.permission consistency
    // =========================================================
    try {
        if (Notification.permission === 'default') {
            Object.defineProperty(Notification, 'permission', {
                get: () => 'default',
                configurable: true,
            });
        }
    } catch (e) {}

    // =========================================================
    // 19. Screen properties — ensure realistic values
    // =========================================================
    try {
        Object.defineProperty(screen, 'colorDepth', {
            get: () => 24,
            configurable: true,
        });
        Object.defineProperty(screen, 'pixelDepth', {
            get: () => 24,
            configurable: true,
        });
    } catch (e) {}

    // =========================================================
    // 20. toString spoofing for patched methods (anti-detection of patches)
    // =========================================================
    try {
        const nativeToString = Function.prototype.toString;
        const nativeToStringStr = nativeToString.call(Function.prototype.toString);
        const patchedMethods = [];
        try { patchedMethods.push(navigator.permissions.query); } catch(e) {}
        try { patchedMethods.push(WebGLRenderingContext.prototype.getParameter); } catch(e) {}
        try {
            if (typeof WebGL2RenderingContext !== 'undefined') {
                patchedMethods.push(WebGL2RenderingContext.prototype.getParameter);
            }
        } catch(e) {}
        try { patchedMethods.push(WebGLRenderingContext.prototype.getExtension); } catch(e) {}

        for (const method of patchedMethods) {
            if (method && method.toString) {
                const methodName = method.name || '';
                method.toString = () => 'function ' + methodName + '() { [native code] }';
            }
        }

        // Patch Function.prototype.toString itself so it looks native
        Function.prototype.toString.toString = () => nativeToStringStr;
    } catch (e) {}

    // =========================================================
    // 21. Error stack trace cleaning — remove playwright references
    // =========================================================
    try {
        const originalError = Error;
        const originalStack = Object.getOwnPropertyDescriptor(originalError.prototype, 'stack');
        if (originalStack && originalStack.get) {
            Object.defineProperty(originalError.prototype, 'stack', {
                get: function() {
                    const stack = originalStack.get.call(this);
                    if (typeof stack === 'string') {
                        return stack.replace(/.*playwright.*/gi, '').replace(/.*pptr.*/gi, '');
                    }
                    return stack;
                },
                configurable: true,
            });
        }
    } catch (e) {}

    // =========================================================
    // 22. navigator.userAgentData (Chrome 90+ — UA Client Hints)
    // =========================================================
    try {
        if (!navigator.userAgentData) {
            Object.defineProperty(navigator, 'userAgentData', {
                get: () => ({
                    brands: [
                        { brand: 'Google Chrome', version: '131' },
                        { brand: 'Chromium', version: '131' },
                        { brand: 'Not_A Brand', version: '24' },
                    ],
                    mobile: false,
                    platform: 'Windows',
                    getHighEntropyValues: () => Promise.resolve({
                        architecture: 'x86',
                        bitness: '64',
                        brands: [
                            { brand: 'Google Chrome', version: '131' },
                            { brand: 'Chromium', version: '131' },
                            { brand: 'Not_A Brand', version: '24' },
                        ],
                        fullVersionList: [
                            { brand: 'Google Chrome', version: '131.0.0.0' },
                            { brand: 'Chromium', version: '131.0.0.0' },
                        ],
                        mobile: false,
                        platform: 'Windows',
                        platformVersion: '15.0.0',
                        uaFullVersion: '131.0.0.0',
                    }),
                }),
                configurable: true,
            });
        }
    } catch (e) {}

    // =========================================================
    // 23. window.outerWidth/outerHeight (headless has outerWidth=0)
    // =========================================================
    try {
        if (window.outerWidth === 0) {
            Object.defineProperty(window, 'outerWidth', {
                get: () => window.innerWidth,
                configurable: true,
            });
        }
        if (window.outerHeight === 0) {
            Object.defineProperty(window, 'outerHeight', {
                get: () => window.innerHeight + 85,
                configurable: true,
            });
        }
    } catch (e) {}

})();
"""
