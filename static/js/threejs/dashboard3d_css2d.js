/**
 * Three.js Dashboard with CSS2DRenderer - Clean rebuild
 * Using proper coordinate system alignment
 */

import * as THREE from 'three';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';

class CSS2DDashboard {
    constructor() {
        this.scene = new THREE.Scene();
        this.camera = null;
        this.renderer = null;
        this.css2dRenderer = null;
        this.container = document.getElementById('threejs-container');
        this.particleSystems = [];
        
        this.init();
    }
    
    init() {
        // Dark navy background
        this.scene.background = new THREE.Color(0x0a0a15);
        
        // Setup perspective camera
        this.camera = new THREE.PerspectiveCamera(
            75,
            window.innerWidth / window.innerHeight,
            0.1,
            2000
        );
        this.camera.position.set(0, 0, 550);
        this.camera.lookAt(0, 0, 0);
        
        // Setup WebGL renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.container.appendChild(this.renderer.domElement);
        
        // Setup CSS2D renderer for HTML overlays
        this.css2dRenderer = new CSS2DRenderer();
        this.css2dRenderer.setSize(window.innerWidth, window.innerHeight);
        this.css2dRenderer.domElement.style.position = 'absolute';
        this.css2dRenderer.domElement.style.top = '0px';
        this.css2dRenderer.domElement.style.pointerEvents = 'none';
        this.container.appendChild(this.css2dRenderer.domElement);
        
        // Add grid background
        this.createGridBackground();
        
        // Create KPI cards with proper CSS2D positioning
        this.createKPICards();
        
        // Start animation loop
        this.animate();
        
        // Setup resize and controls
        window.addEventListener('resize', () => this.onWindowResize());
        this.setupCameraControls();
    }
    
    createKPICards() {
        const cardData = [
            { label: 'Availability', value: '95%', color: 0x00ffff },
            { label: 'Performance', value: '88%', color: 0x00ffff },
            { label: 'Quality', value: '98%', color: 0x00ffff },
            { label: 'Overall OEE', value: '82%', color: 0x00ffff }
        ];
        
        const cardWidth = 200;
        const cardHeight = 150;
        const spacing = 250;
        const startX = -(cardData.length - 1) * spacing / 2;
        
        cardData.forEach((card, index) => {
            const cardGroup = new THREE.Group();
            
            // 3D Border frame
            this.createCardBorder(cardGroup, cardWidth, cardHeight, card.color);
            
            // HTML content using CSS2DObject (working approach)
            this.createCardContent(cardGroup, card, cardWidth, cardHeight);
            
            // Position the entire card
            cardGroup.position.set(startX + (index * spacing), 250, 0);
            this.scene.add(cardGroup);
            
            // Add separate sparkline below the card using regular HTML positioning
            this.createSparklineBelow(startX + (index * spacing), 250, card, cardWidth, cardHeight);
        });
    }
    
    createCardBorder(cardGroup, width, height, color) {
        // Irregular bracket dimensions for unstable light effect
        const baseBracketLength = 20;
        const bracketWidth = 0.3; // Razor thin like pure light
        
        // Create irregular variations for each bracket
        const bracketVariations = {
            tlH: { length: baseBracketLength + Math.random() * 8 - 4, offset: Math.random() * 6 - 3 },
            tlV: { length: baseBracketLength + Math.random() * 8 - 4, offset: Math.random() * 6 - 3 },
            trH: { length: baseBracketLength + Math.random() * 8 - 4, offset: Math.random() * 6 - 3 },
            trV: { length: baseBracketLength + Math.random() * 8 - 4, offset: Math.random() * 6 - 3 },
            blH: { length: baseBracketLength + Math.random() * 8 - 4, offset: Math.random() * 6 - 3 },
            blV: { length: baseBracketLength + Math.random() * 8 - 4, offset: Math.random() * 6 - 3 },
            brH: { length: baseBracketLength + Math.random() * 8 - 4, offset: Math.random() * 6 - 3 },
            brV: { length: baseBracketLength + Math.random() * 8 - 4, offset: Math.random() * 6 - 3 }
        };
        
        // Store variations for animation
        cardGroup.userData.bracketVariations = bracketVariations;
        
        // Create glowing material for brackets
        const bracketMaterial = new THREE.MeshBasicMaterial({ 
            color: color,
            transparent: true,
            opacity: 0.9,
            blending: THREE.AdditiveBlending
        });
        
        // TOP-LEFT CORNER L-bracket
        const tlHorizontal = new THREE.PlaneGeometry(bracketVariations.tlH.length, bracketWidth);
        const tlHorizontalMesh = new THREE.Mesh(tlHorizontal, bracketMaterial.clone());
        tlHorizontalMesh.position.set(-width/2 + bracketVariations.tlH.length/2 + bracketVariations.tlH.offset, height/2, 1);
        
        const tlVertical = new THREE.PlaneGeometry(bracketWidth, bracketVariations.tlV.length);
        const tlVerticalMesh = new THREE.Mesh(tlVertical, bracketMaterial.clone());
        tlVerticalMesh.position.set(-width/2 + bracketVariations.tlV.offset, height/2 - bracketVariations.tlV.length/2, 1);
        
        // TOP-RIGHT CORNER L-bracket
        const trHorizontal = new THREE.PlaneGeometry(bracketVariations.trH.length, bracketWidth);
        const trHorizontalMesh = new THREE.Mesh(trHorizontal, bracketMaterial.clone());
        trHorizontalMesh.position.set(width/2 - bracketVariations.trH.length/2 + bracketVariations.trH.offset, height/2, 1);
        
        const trVertical = new THREE.PlaneGeometry(bracketWidth, bracketVariations.trV.length);
        const trVerticalMesh = new THREE.Mesh(trVertical, bracketMaterial.clone());
        trVerticalMesh.position.set(width/2 + bracketVariations.trV.offset, height/2 - bracketVariations.trV.length/2, 1);
        
        // BOTTOM-LEFT CORNER L-bracket
        const blHorizontal = new THREE.PlaneGeometry(bracketVariations.blH.length, bracketWidth);
        const blHorizontalMesh = new THREE.Mesh(blHorizontal, bracketMaterial.clone());
        blHorizontalMesh.position.set(-width/2 + bracketVariations.blH.length/2 + bracketVariations.blH.offset, -height/2, 1);
        
        const blVertical = new THREE.PlaneGeometry(bracketWidth, bracketVariations.blV.length);
        const blVerticalMesh = new THREE.Mesh(blVertical, bracketMaterial.clone());
        blVerticalMesh.position.set(-width/2 + bracketVariations.blV.offset, -height/2 + bracketVariations.blV.length/2, 1);
        
        // BOTTOM-RIGHT CORNER L-bracket
        const brHorizontal = new THREE.PlaneGeometry(bracketVariations.brH.length, bracketWidth);
        const brHorizontalMesh = new THREE.Mesh(brHorizontal, bracketMaterial.clone());
        brHorizontalMesh.position.set(width/2 - bracketVariations.brH.length/2 + bracketVariations.brH.offset, -height/2, 1);
        
        const brVertical = new THREE.PlaneGeometry(bracketWidth, bracketVariations.brV.length);
        const brVerticalMesh = new THREE.Mesh(brVertical, bracketMaterial.clone());
        brVerticalMesh.position.set(width/2 + bracketVariations.brV.offset, -height/2 + bracketVariations.brV.length/2, 1);
        
        // Add all bracket pieces to card group
        cardGroup.add(tlHorizontalMesh);
        cardGroup.add(tlVerticalMesh);
        cardGroup.add(trHorizontalMesh);
        cardGroup.add(trVerticalMesh);
        cardGroup.add(blHorizontalMesh);
        cardGroup.add(blVerticalMesh);
        cardGroup.add(brHorizontalMesh);
        cardGroup.add(brVerticalMesh);
        
        // Store bracket meshes for animation
        cardGroup.userData.brackets = [
            tlHorizontalMesh, tlVerticalMesh,
            trHorizontalMesh, trVerticalMesh,
            blHorizontalMesh, blVerticalMesh,
            brHorizontalMesh, brVerticalMesh
        ];
        
        // Create hot spots for laser tips
        const hotSpots = [];
        for (let i = 0; i < 8; i++) {
            const hotSpotGeometry = new THREE.CircleGeometry(1.5, 8);
            const hotSpotMaterial = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.8,
                blending: THREE.AdditiveBlending
            });
            const hotSpot = new THREE.Mesh(hotSpotGeometry, hotSpotMaterial);
            cardGroup.add(hotSpot);
            hotSpots.push(hotSpot);
        }
        
        cardGroup.userData.hotSpots = hotSpots;
    }
    
    createCardContent(cardGroup, cardData, width, height) {
        // Create simple HTML content div (no sparklines yet)
        const contentDiv = document.createElement('div');
        contentDiv.style.width = width + 'px';
        contentDiv.style.height = height + 'px';
        contentDiv.style.backgroundColor = 'transparent';
        contentDiv.style.border = 'none';
        contentDiv.style.borderRadius = '0';
        contentDiv.style.padding = '20px';
        contentDiv.style.boxSizing = 'border-box';
        contentDiv.style.display = 'flex';
        contentDiv.style.flexDirection = 'column';
        contentDiv.style.justifyContent = 'space-between';
        
        // Header
        const header = document.createElement('div');
        header.style.color = '#00ffff';
        header.style.fontSize = '12px';
        header.style.fontWeight = '600';
        header.style.textTransform = 'uppercase';
        header.style.letterSpacing = '1px';
        header.textContent = cardData.label;
        
        // Main value
        const value = document.createElement('div');
        value.style.color = '#00ffff';
        value.style.fontSize = '3rem';
        value.style.fontWeight = '700';
        value.style.textAlign = 'center';
        value.style.textShadow = '0 0 15px #00ffff';
        value.textContent = cardData.value;
        
        contentDiv.appendChild(header);
        contentDiv.appendChild(value);
        
        // Create CSS2DObject and attach to card group
        const css2dObject = new CSS2DObject(contentDiv);
        css2dObject.position.set(0, 0, 0); // Same Z plane as brackets
        css2dObject.center.set(0.5, 0.5); // Center alignment
        
        cardGroup.add(css2dObject);
    }
    
    createSparklineBelow(worldX, worldY, cardData, cardWidth, cardHeight) {
        // Convert world position to screen coordinates (manual calculation)
        const screenX = worldX + (window.innerWidth / 2) - (cardWidth / 2) + 40; // Center with padding
        const screenY = (window.innerHeight / 2) - worldY + (cardHeight / 2) - 40; // Below the card
        
        // Create sparkline container using regular HTML positioning
        const sparklineDiv = document.createElement('div');
        sparklineDiv.style.position = 'absolute';
        sparklineDiv.style.left = screenX + 'px';
        sparklineDiv.style.top = screenY + 'px';
        sparklineDiv.style.width = '100px';
        sparklineDiv.style.height = '20px';
        sparklineDiv.style.pointerEvents = 'none';
        sparklineDiv.style.zIndex = '101';
        
        const canvas = document.createElement('canvas');
        canvas.width = 100;
        canvas.height = 20;
        canvas.style.width = '100px';
        canvas.style.height = '20px';
        
        sparklineDiv.appendChild(canvas);
        document.body.appendChild(sparklineDiv);
        
        // Draw sparkline
        this.drawSparkline(canvas, cardData.label, cardData.color);
    }
    
    drawSparkline(canvas, label, color) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        const data = {
            'Availability': [88, 90, 92, 89, 93, 91, 95],
            'Performance': [92, 88, 90, 87, 89, 85, 88], 
            'Quality': [94, 96, 95, 97, 95, 96, 98],
            'Overall OEE': [82, 84, 86, 83, 87, 85, 82]
        }[label] || [];
        
        if (data.length === 0) return;
        
        const hexColor = '#' + color.toString(16).padStart(6, '0');
        const min = Math.min(...data);
        const max = Math.max(...data);
        const range = max - min || 1;
        
        ctx.strokeStyle = hexColor;
        ctx.lineWidth = 1;
        ctx.shadowColor = hexColor;
        ctx.shadowBlur = 2;
        
        ctx.beginPath();
        data.forEach((value, index) => {
            const x = (index * canvas.width / (data.length - 1));
            const y = canvas.height - ((value - min) / range * canvas.height);
            if (index === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();
    }
    
    
    createGridBackground() {
        const gridSize = 50;
        const geometry = new THREE.BufferGeometry();
        const material = new THREE.LineBasicMaterial({ 
            color: 0x1a1a2e, 
            transparent: true, 
            opacity: 0.08 
        });
        
        const points = [];
        
        // Create grid lines
        for (let i = -1000; i <= 1000; i += gridSize) {
            points.push(i, -500, -100, i, 500, -100);
            points.push(-1000, i, -100, 1000, i, -100);
        }
        
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
        const grid = new THREE.LineSegments(geometry, material);
        this.scene.add(grid);
    }
    
    setupCameraControls() {
        // Camera position display
        const positionDisplay = document.createElement('div');
        positionDisplay.id = 'camera-position';
        positionDisplay.style.position = 'fixed';
        positionDisplay.style.top = '10px';
        positionDisplay.style.left = '10px';
        positionDisplay.style.background = 'rgba(0,0,0,0.8)';
        positionDisplay.style.color = '#00ffff';
        positionDisplay.style.padding = '10px';
        positionDisplay.style.fontFamily = 'monospace';
        positionDisplay.style.fontSize = '12px';
        positionDisplay.style.zIndex = '1000';
        document.body.appendChild(positionDisplay);
        
        this.updatePositionDisplay();
        
        // Keyboard controls
        document.addEventListener('keydown', (event) => {
            const step = 50;
            switch(event.key.toLowerCase()) {
                case 'w': this.camera.position.y += step; break;
                case 's': this.camera.position.y -= step; break;
                case 'a': this.camera.position.x -= step; break;
                case 'd': this.camera.position.x += step; break;
                case 'q': this.camera.position.z += step; break;
                case 'e': this.camera.position.z -= step; break;
                case 'r': this.camera.position.set(0, 0, 550); break;
                case ' ': 
                    event.preventDefault();
                    console.log('Current camera position:', this.camera.position);
                    break;
            }
            this.camera.lookAt(0, 0, 0);
            this.updatePositionDisplay();
        });
    }
    
    updatePositionDisplay() {
        const display = document.getElementById('camera-position');
        if (display) {
            display.innerHTML = `
                Camera: x=${Math.round(this.camera.position.x)}, y=${Math.round(this.camera.position.y)}, z=${Math.round(this.camera.position.z)}<br>
                <strong>Controls:</strong><br>
                WASD: Move camera<br>
                QE: Forward/Back<br>
                R: Reset<br>
                Space: Log position
            `;
        }
    }
    
    onWindowResize() {
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.css2dRenderer.setSize(window.innerWidth, window.innerHeight);
    }
    
    animate() {
        requestAnimationFrame(() => this.animate());
        
        // Animate dynamic light brackets
        this.animateDynamicLightFrames();
        
        // Render both WebGL and CSS2D
        this.renderer.render(this.scene, this.camera);
        this.css2dRenderer.render(this.scene, this.camera);
    }
    
    animateDynamicLightFrames() {
        const time = Date.now() * 0.001;
        
        this.scene.traverse((object) => {
            if (object.userData.brackets && object.userData.hotSpots) {
                const brackets = object.userData.brackets;
                const hotSpots = object.userData.hotSpots;
                const variations = object.userData.bracketVariations;
                const cardIndex = object.position.x;
                const cardPhase = cardIndex * 0.2;
                
                brackets.forEach((bracket, index) => {
                    // Get original variation data
                    const bracketKeys = ['tlH', 'tlV', 'trH', 'trV', 'blH', 'blV', 'brH', 'brV'];
                    const variation = variations[bracketKeys[index]];
                    
                    // Dynamic extension/retraction - 75% slower
                    const extensionPhase = time * 0.4 + cardPhase + index * 0.3;
                    const maxExtension = (index % 2 === 0) ? 240 : 180; // Full card width/height
                    const extensionFactor = Math.sin(extensionPhase) * 0.5 + 0.5; // 0 to 1
                    const newLength = variation.length + (maxExtension - variation.length) * extensionFactor;
                    
                    // Update geometry for natural extension
                    if (index % 2 === 0) {
                        // Horizontal brackets - extend toward center only
                        bracket.geometry = new THREE.PlaneGeometry(Math.max(2, newLength), 0.3);
                        // Keep outer edge fixed, extend toward center
                        if (index === 0 || index === 4) { // Left brackets
                            bracket.position.x = -240/2 + newLength/2 + variation.offset;
                        } else { // Right brackets (index 2, 6)
                            bracket.position.x = 240/2 - newLength/2 + variation.offset;
                        }
                    } else {
                        // Vertical brackets - extend toward center only
                        bracket.geometry = new THREE.PlaneGeometry(0.3, Math.max(2, newLength));
                        // Keep outer edge fixed, extend toward center
                        if (index === 1 || index === 3) { // Top brackets
                            bracket.position.y = 180/2 - newLength/2 + variation.offset;
                        } else { // Bottom brackets (index 5, 7)
                            bracket.position.y = -180/2 + newLength/2 + variation.offset;
                        }
                    }
                    
                    // Dynamic opacity flickering
                    const flickerPhase = time * 6 + index * 0.8;
                    const flicker = Math.sin(flickerPhase) * 0.2 + 0.8; // 0.6 to 1.0
                    bracket.material.opacity = flicker;
                });
                
                // Animate hot spots to follow bracket extensions - 87.5% slower total
                hotSpots.forEach((hotSpot, index) => {
                    const targetBracket = brackets[index];
                    const hotSpotPhase = time * 1 + cardPhase + index * 0.5;
                    
                    // Hot spot intensity pulsing with disappearing periods
                    const pulseValue = Math.sin(hotSpotPhase);
                    const intensity = pulseValue > 0 ? pulseValue * 0.8 + 0.2 : 0; // Disappears when negative
                    hotSpot.material.opacity = intensity;
                    
                    // Hot spot size pulsing
                    const sizePulse = Math.sin(hotSpotPhase * 1.5) * 0.3 + 1.0; // 0.7 to 1.3
                    hotSpot.scale.set(sizePulse, sizePulse, sizePulse);
                    
                    // Position hot spot at the extending end of the bracket
                    const bracketKeys = ['tlH', 'tlV', 'trH', 'trV', 'blH', 'blV', 'brH', 'brV'];
                    const variation = variations[bracketKeys[index]];
                    const extensionPhase = time * 0.4 + cardPhase + index * 0.3;
                    const maxExtension = (index % 2 === 0) ? 240 : 180;
                    const extensionFactor = Math.sin(extensionPhase) * 0.5 + 0.5;
                    const currentLength = variation.length + (maxExtension - variation.length) * extensionFactor;
                    
                    // Position hot spot at the tip of the extending bracket
                    if (index % 2 === 0) {
                        // Horizontal brackets - hot spot at end
                        if (index === 0 || index === 4) { // Left brackets
                            hotSpot.position.set(-240/2 + currentLength + variation.offset, targetBracket.position.y, 2);
                        } else { // Right brackets  
                            hotSpot.position.set(240/2 - currentLength + variation.offset, targetBracket.position.y, 2);
                        }
                    } else {
                        // Vertical brackets - hot spot at end
                        if (index === 1 || index === 3) { // Top brackets
                            hotSpot.position.set(targetBracket.position.x, 180/2 - currentLength + variation.offset, 2);
                        } else { // Bottom brackets
                            hotSpot.position.set(targetBracket.position.x, -180/2 + currentLength + variation.offset, 2);
                        }
                    }
                });
            }
        });
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('Three.js version:', THREE.REVISION);
    console.log('Initializing CSS2D Dashboard');
    
    try {
        new CSS2DDashboard();
        console.log('CSS2D dashboard initialized successfully');
    } catch (error) {
        console.error('Failed to initialize CSS2D dashboard:', error);
    }
});