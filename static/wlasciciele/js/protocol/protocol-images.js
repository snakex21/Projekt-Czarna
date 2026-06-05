/**
 * Skany protokołu właściciela (P2.7 Etap 3/5C).
 *
 * Moduł obsługuje wyszukiwanie skanów, modal obrazu, Panzoom i nawigację
 * między stronami protokołu. Korzysta z `window.OwnersAPI`.
 */
(function () {
    'use strict';

    const API = window.OwnersAPI;

    let ownerKey = null;
    let elements = {
        showOriginalBtn: null,
        imageModal: null,
        modalImage: null,
        closeModalBtn: null,
        prevBtn: null,
        nextBtn: null,
        pageCounter: null,
    };
    let currentSession = null;
    let panzoomInstance = null;

    function init(options) {
        const config = options || {};
        ownerKey = config.ownerKey || ownerKey;
        elements = Object.assign({}, elements, config.elements || {});
        const session = {
            ownerKey: ownerKey,
            elements: Object.assign({}, elements),
            imageUrls: [],
            currentImageIndex: 0,
        };
        currentSession = session;
        bindEvents(session);
        return session;
    }

    function bindEvents(session) {
        const boundElements = session.elements;
        if (boundElements.showOriginalBtn && !boundElements.showOriginalBtn.dataset.protocolImagesBound) {
            boundElements.showOriginalBtn.addEventListener('click', () => open(session));
            boundElements.showOriginalBtn.dataset.protocolImagesBound = 'true';
        }
        if (boundElements.closeModalBtn && !boundElements.closeModalBtn.dataset.protocolImagesBound) {
            boundElements.closeModalBtn.addEventListener('click', close);
            boundElements.closeModalBtn.dataset.protocolImagesBound = 'true';
        }
        if (boundElements.imageModal && !boundElements.imageModal.dataset.protocolImagesBound) {
            boundElements.imageModal.addEventListener('click', (event) => {
                if (event.target === boundElements.imageModal) close();
            });
            boundElements.imageModal.dataset.protocolImagesBound = 'true';
        }
        if (boundElements.prevBtn && !boundElements.prevBtn.dataset.protocolImagesBound) {
            boundElements.prevBtn.addEventListener('click', prev);
            boundElements.prevBtn.dataset.protocolImagesBound = 'true';
        }
        if (boundElements.nextBtn && !boundElements.nextBtn.dataset.protocolImagesBound) {
            boundElements.nextBtn.addEventListener('click', next);
            boundElements.nextBtn.dataset.protocolImagesBound = 'true';
        }
    }

    function find(targetSession) {
        const session = targetSession || currentSession;
        const found = [];
        let i = 1;

        const checkNext = () => {
            const img = new Image();
            ownerKey = session.ownerKey;
            img.src = API.protocolScan(ownerKey, i);

            img.onload = () => {
                found.push(img.src);
                i++;
                checkNext();
            };

            img.onerror = () => {
                if (i === 1 && found.length === 0) {
                    const singleImg = new Image();
                    singleImg.src = API.protocolScanSingle(ownerKey);

                    singleImg.onload = () => {
                        found.push(singleImg.src);
                        finish(found, session);
                    };

                    singleImg.onerror = () => finish(found, session);
                } else {
                    finish(found, session);
                }
            };
        };

        checkNext();
    }

    function finish(foundImages, targetSession) {
        const session = targetSession || currentSession;
        session.imageUrls = foundImages;
        if (session.imageUrls.length > 0 && session.elements.showOriginalBtn) {
            session.elements.showOriginalBtn.classList.remove('hidden');
        }
    }

    function open(targetSession) {
        const session = targetSession || currentSession;
        currentSession = session;
        if (session.imageUrls.length === 0) {
            alert(`Brak skanów protokołu dla tego właściciela.\nOczekiwane pliki: ${API.protocolScan(session.ownerKey, 1)}, 2.jpg, ...`);
            return;
        }

        session.currentImageIndex = 0;
        updateModalContent(session);
        session.elements.imageModal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';

        panzoomInstance = Panzoom(session.elements.modalImage, {
            maxScale: 5,
            minScale: 0.5,
        });

        session.elements.modalImage.parentElement.addEventListener('wheel', panzoomInstance.zoomWithWheel);
    }

    function close() {
        const session = currentSession;
        if (!session || !session.elements.imageModal) return;
        session.elements.imageModal.classList.add('hidden');
        document.body.style.overflow = 'auto';

        if (panzoomInstance) {
            panzoomInstance.destroy();
            panzoomInstance = null;
        }
    }

    function updateModalContent(targetSession) {
        const session = targetSession || currentSession;
        session.elements.modalImage.src = session.imageUrls[session.currentImageIndex];
        session.elements.pageCounter.textContent = `Strona ${session.currentImageIndex + 1} / ${session.imageUrls.length}`;

        session.elements.prevBtn.disabled = session.currentImageIndex === 0;
        session.elements.nextBtn.disabled = session.currentImageIndex === session.imageUrls.length - 1;

        const navControls = document.querySelector('.modal-nav-controls');
        if (navControls) navControls.style.display = session.imageUrls.length > 1 ? 'flex' : 'none';
    }

    function next() {
        const session = currentSession;
        if (session.currentImageIndex < session.imageUrls.length - 1) {
            session.currentImageIndex++;
            updateModalContent(session);
            if (panzoomInstance) panzoomInstance.reset();
        }
    }

    function prev() {
        const session = currentSession;
        if (session.currentImageIndex > 0) {
            session.currentImageIndex--;
            updateModalContent(session);
            if (panzoomInstance) panzoomInstance.reset();
        }
    }

    window.ProtocolImages = Object.freeze({
        init: init,
        find: find,
        open: open,
        close: close,
        next: next,
        prev: prev,
    });
})();
