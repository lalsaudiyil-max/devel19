/** @odoo-module **/

(function() {
    "use strict";

    // 1. Cross-Browser Permissions Safety Patch.
    if (window.navigator && window.navigator.permissions && window.navigator.permissions.query) {
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = function(descriptor) {
            if (descriptor && (descriptor.name === 'camera' || descriptor.name === 'microphone')) {
                if (navigator.userAgent.indexOf("Firefox") !== -1) {
                    return Promise.reject(new TypeError("Bypassed unsupported Firefox permission enum"));
                }
            }
            return originalQuery.call(window.navigator.permissions, descriptor);
        };
    }

    // 2. Hardware-Locked Canvas Fingerprint Generator
    function getHardwareFingerprint() {
        let fingerprint = "";
        try {
            // Create a hidden canvas element
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            
            // Draw a complex geometric shape with text to trigger unique font/hardware rendering
            canvas.width = 200;
            canvas.height = 50;
            ctx.textBaseline = "top";
            ctx.font = "14px 'Arial', 'Helvetica', sans-serif";
            ctx.fillStyle = "#f60";
            ctx.fillRect(125, 1, 62, 20);
            ctx.fillStyle = "#069";
            ctx.fillText("OdooGatekeeperV19_#1!", 2, 15);
            ctx.fillStyle = "rgba(102, 204, 0, 0.7)";
            ctx.fillText("OdooGatekeeperV19_#1!", 4, 17);
            
            // Convert the rendered image canvas space to a unique base64 text string
            const b64 = canvas.toDataURL();
            
            // Generate a simple hash from the base64 string
            let hash = 0;
            for (let i = 0; i < b64.length; i++) {
                hash = (hash << 5) - hash + b64.charCodeAt(i);
                hash |= 0; // Convert to 32bit integer
            }
            fingerprint = "hw-hash-" + Math.abs(hash);
        } catch (e) {
            // Fallback if canvas is blocked by extreme browser configurations
            fingerprint = "hw-fallback-" + navigator.userAgent.replace(/[^a-zA-Z0-9]/g, "").slice(0, 20);
        }

        // Extract system profile attributes
        let userAgent = navigator.userAgent;
        let platform = "Unknown OS";
        if (userAgent.indexOf("Win") != -1) platform = "Windows";
        else if (userAgent.indexOf("Mac") != -1) platform = "MacOS";
        else if (userAgent.indexOf("Linux") != -1) platform = "Linux";
        
        let browser = "Browser";
        if (userAgent.indexOf("Chrome") != -1) browser = "Chrome";
        else if (userAgent.indexOf("Firefox") != -1) browser = "Firefox";
        else if (userAgent.indexOf("Safari") != -1) browser = "Safari";
        
        return {
            uuid: fingerprint,
            name: platform + " (" + browser + ")"
        };
    }

    // 3. Fallback Form Input Synchronization
    function updatePhysicalFormInputs() {
        try {
            const form = document.querySelector('form.oe_login_form');
            if (!form) return;
            
            let metrics = getHardwareFingerprint();
            let uEl = document.getElementById('forced_hw_uuid');
            if (!uEl) {
                uEl = document.createElement('input');
                uEl.type = 'hidden'; uEl.name = 'hardware_uuid'; uEl.id = 'forced_hw_uuid';
                form.appendChild(uEl);
            }
            uEl.value = metrics.uuid;

            let nEl = document.getElementById('forced_comp_name');
            if (!nEl) {
                nEl = document.createElement('input');
                nEl.type = 'hidden'; nEl.name = 'computer_name'; nEl.id = 'forced_comp_name';
                form.appendChild(nEl);
            }
            nEl.value = metrics.name;
        } catch(e) {}
    }

    // 4. Hook Network Requests globally to append fingerprint keys mid-flight
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
        let url = args[0];
        let options = args[1];
        if (url && typeof url === 'string' && url.indexOf('/web/login') !== -1 && options && options.body) {
            let metrics = getHardwareFingerprint();
            if (options.body instanceof FormData) {
                options.body.set('hardware_uuid', metrics.uuid);
                options.body.set('computer_name', metrics.name);
            } else if (typeof options.body === 'string') {
                if (options.body.indexOf('hardware_uuid') === -1) {
                    options.body += '&hardware_uuid=' + encodeURIComponent(metrics.uuid) + '&computer_name=' + encodeURIComponent(metrics.name);
                }
            }
        }
        return originalFetch.apply(this, args);
    };

    // Bind initialization hooks across interaction levels
    document.addEventListener('DOMContentLoaded', updatePhysicalFormInputs);
    document.addEventListener('input', updatePhysicalFormInputs, true);
    document.addEventListener('focusin', updatePhysicalFormInputs, true);
    document.addEventListener('click', updatePhysicalFormInputs, true);
})();
