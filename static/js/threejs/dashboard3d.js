/**
 * Three.js Dashboard - Phase 1
 * Identical recreation of HTML/Canvas dashboard using Three.js
 */

class ThreeJSDashboard {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.viewport = {
            width: window.innerWidth,
            height: window.innerHeight
        };
        
        // Store original dashboard dimensions
        this.sections = {
            topKPI: { height: this.viewport.height * 0.22, yStart: this.viewport.height * 0.78 },
            middle: { height: this.viewport.height * 0.23, yStart: this.viewport.height * 0.55 },
            machineRail: { height: this.viewport.height * 0.18, yStart: 0 }
        };
        
        this.components = {};
        this.animationId = null;
        
        this.init();
    }
    
    init() {
        this.setupScene();
        this.setupCamera();
        this.setupRenderer();
        this.setupLighting();
        this.setupEventListeners();
        
        // Start with Phase 1 test component
        this.createTestKPICard();
        
        this.animate();
    }
    
    setupScene() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xf8f9fa); // Match original background
    }
    
    setupCamera() {
        // Use orthographic camera for exact 2D positioning
        const aspect = this.viewport.width / this.viewport.height;
        const frustumSize = this.viewport.height;
        
        this.camera = new THREE.OrthographicCamera(
            frustumSize * aspect / -2,  // left
            frustumSize * aspect / 2,   // right
            frustumSize / 2,            // top
            frustumSize / -2,           // bottom
            1,                          // near
            1000                        // far
        );
        
        this.camera.position.z = 10;
    }
    
    setupRenderer() {
        this.renderer = new THREE.WebGLRenderer({ 
            antialias: true,
            alpha: true
        });
        this.renderer.setSize(this.viewport.width, this.viewport.height);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.container.appendChild(this.renderer.domElement);
    }
    
    setupLighting() {
        // Bright ambient light for flat 2D appearance
        const ambientLight = new THREE.AmbientLight(0xffffff, 1.0);
        this.scene.add(ambientLight);
    }
    
    setupEventListeners() {
        window.addEventListener('resize', () => this.onWindowResize());
    }
    
    // Convert HTML coordinates to Three.js world space
    htmlToWorld(htmlX, htmlY) {
        const worldX = (htmlX - this.viewport.width / 2);
        const worldY = -(htmlY - this.viewport.height / 2);
        return { x: worldX, y: worldY };
    }
    
    createTestKPICard() {
        // Create test KPI card that exactly matches original
        const cardGroup = new THREE.Group();
        
        // Card background - exact dimensions from original CSS
        const cardWidth = 280; // Approximate col-3 width
        const cardHeight = 140; // Match original card height
        
        const cardGeometry = new THREE.PlaneGeometry(cardWidth, cardHeight);
        const cardMaterial = new THREE.MeshBasicMaterial({ 
            color: 0xffffff,
            transparent: true,
            opacity: 1.0
        });
        const cardMesh = new THREE.Mesh(cardGeometry, cardMaterial);
        
        // Add subtle shadow effect (matching original box-shadow)
        const shadowGeometry = new THREE.PlaneGeometry(cardWidth + 4, cardHeight + 4);
        const shadowMaterial = new THREE.MeshBasicMaterial({ 
            color: 0x000000,
            transparent: true,
            opacity: 0.1
        });
        const shadowMesh = new THREE.Mesh(shadowGeometry, shadowMaterial);
        shadowMesh.position.set(2, -2, -0.1);
        
        cardGroup.add(shadowMesh);
        cardGroup.add(cardMesh);
        
        // Add border radius effect using multiple small planes (simple approach)
        // For Phase 1, we'll use a simple rectangular card
        
        // Position card in top-left KPI position (matching original layout)
        const topSectionY = this.viewport.height * 0.78;
        const cardPos = this.htmlToWorld(200, topSectionY - 70);
        cardGroup.position.set(cardPos.x, cardPos.y, 0);
        
        this.scene.add(cardGroup);
        this.components.testCard = cardGroup;
        
        // Add title text using HTML overlay approach
        this.addCardText(cardGroup);
    }
    
    // Remove loadFont method - not needed for Phase 1
    
    addCardText(cardGroup) {
        // Phase 1: Create HTML overlay for text (hybrid approach)
        const textOverlay = document.createElement('div');
        textOverlay.style.position = 'absolute';
        textOverlay.style.left = '50px';
        textOverlay.style.top = '100px';
        textOverlay.style.color = '#6c757d';
        textOverlay.style.fontSize = '14px';
        textOverlay.style.fontWeight = '500';
        textOverlay.style.textTransform = 'uppercase';
        textOverlay.innerHTML = 'Availability';
        
        const valueOverlay = document.createElement('div');
        valueOverlay.style.position = 'absolute';
        valueOverlay.style.left = '50px';
        valueOverlay.style.top = '130px';
        valueOverlay.style.color = '#2d3748';
        valueOverlay.style.fontSize = '4.5rem';
        valueOverlay.style.fontWeight = '700';
        valueOverlay.style.lineHeight = '1';
        valueOverlay.innerHTML = '95%';
        valueOverlay.id = 'threejs-availability-value';
        
        document.body.appendChild(textOverlay);
        document.body.appendChild(valueOverlay);
        
        // Store references for cleanup
        this.components.textOverlays = [textOverlay, valueOverlay];
    }
    
    // Real-time data updates
    startDataUpdates() {
        setInterval(() => {
            this.updateKPIData();
        }, 5000);
    }
    
    updateKPIData() {
        fetch('/api/current-metrics/')
            .then(response => response.json())
            .then(data => {
                // Update the test card value
                const valueEl = document.getElementById('threejs-availability-value');
                if (valueEl && data.availability) {
                    valueEl.textContent = data.availability.toFixed(1) + '%';
                    
                    // Add subtle animation effect
                    valueEl.style.transform = 'scale(1.05)';
                    setTimeout(() => {
                        valueEl.style.transform = 'scale(1)';
                    }, 200);
                }
            })
            .catch(error => {
                console.log('KPI update failed:', error);
            });
    }
    
    onWindowResize() {
        this.viewport.width = window.innerWidth;
        this.viewport.height = window.innerHeight;
        
        // Update camera
        const aspect = this.viewport.width / this.viewport.height;
        const frustumSize = this.viewport.height;
        
        this.camera.left = frustumSize * aspect / -2;
        this.camera.right = frustumSize * aspect / 2;
        this.camera.top = frustumSize / 2;
        this.camera.bottom = frustumSize / -2;
        this.camera.updateProjectionMatrix();
        
        // Update renderer
        this.renderer.setSize(this.viewport.width, this.viewport.height);
        
        // Reposition components
        this.repositionComponents();
    }
    
    repositionComponents() {
        if (this.components.testCard) {
            const topSectionY = this.viewport.height * 0.78;
            const cardPos = this.htmlToWorld(200, topSectionY - 70);
            this.components.testCard.position.set(cardPos.x, cardPos.y, 0);
        }
    }
    
    animate() {
        this.animationId = requestAnimationFrame(() => this.animate());
        this.renderer.render(this.scene, this.camera);
    }
    
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        
        // Clean up overlays
        if (this.components.textOverlays) {
            this.components.textOverlays.forEach(overlay => {
                overlay.remove();
            });
        }
        
        // Clean up Three.js objects
        this.scene.traverse((object) => {
            if (object.geometry) object.geometry.dispose();
            if (object.material) object.material.dispose();
        });
        
        this.renderer.dispose();
    }
}

// Initialize when DOM is ready
let dashboard3D = null;

document.addEventListener('DOMContentLoaded', function() {
    console.log('Starting Three.js Dashboard - Phase 1');
    dashboard3D = new ThreeJSDashboard('threejs-container');
    dashboard3D.startDataUpdates();
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (dashboard3D) {
        dashboard3D.destroy();
    }
});