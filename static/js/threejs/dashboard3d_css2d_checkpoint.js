/**
 * Three.js Dashboard with CSS2DRenderer - CHECKPOINT VERSION
 * 
 * CHECKPOINT NOTES - WORKING STATE WITH TEMPLATE FIX
 * URL: http://localhost:8000/threejs-dashboard/
 * 
 * This checkpoint represents the FINAL WORKING STATE with all template issues resolved.
 * 
 * TEMPLATE FIXES APPLIED:
 * - Added missing {% load static %} to threejs_dashboard.html (line 1)
 * - Removed base.html inheritance to prevent navigation overlay conflicts
 * - Ensured fullscreen Three.js experience without Django UI interference
 * 
 * CHECKPOINT LOGIC IMPLEMENTED:
 * 
 * 1. TOP SECTION - Dynamic L-Bracket KPI Cards:
 *    - 4 KPI cards with irregular bracket variations (random offsets)
 *    - Extension/retraction animations with 75% slower timing
 *    - Hot spots following bracket tips with disappearing periods
 *    - Unified cyan color scheme (#00ffff) for all brackets and text
 *    - CSS2DObject for HTML content overlay (sparklines, values, labels)
 * 
 * 2. MIDDLE SECTION - Chart.js Integration:
 *    - Chart.js planned vs actual performance chart (676x338 pixels)
 *    - Fixed canvas dimensions with responsive: false to solve scaling issues
 *    - 24-hour timeline with downtime hot spots and NOW line indicator
 *    - Position: chartX = -150, chartY = -25 (optimized through arrow key controls)
 *    - NO BACKGROUND CARD - transparent styling applied
 * 
 * 3. RIGHT SIDE CARDS:
 *    - Active Fault Overlay: Machine name + growing line animation + MTTR/MTBF metrics
 *    - Last Downtime Event: Fault details with time/duration info
 *    - Both cards 300x160 pixels with NO BACKGROUNDS - transparent styling
 *    - Growing line represents downtime duration with pulsing glow effect
 * 
 * 4. COORDINATE SYSTEM:
 *    - CSS2DRenderer for HTML overlay positioning
 *    - PerspectiveCamera at (0, 0, 550) looking at origin
 *    - Manual positioning for chart and cards in 3D space
 * 
 * 5. ANIMATION SYSTEMS:
 *    - animateDynamicLightFrames(): Extension/retraction of top section brackets
 *    - animateFaultDurationLine(): Growing line progress bar with pulsing glow
 *    - Hot spot following bracket tips with intensity pulsing
 * 
 * USER FEEDBACK HISTORY:
 * - "ok beautiful" - User approval of subtle frames before 3D attempt
 * - "i dont see any difference" then "i see. i dont liek it. revert the change" - 3D rejection
 * - "why is it opening two pages when i click that link" - Template inheritance issue
 * 
 * WHAT WAS REJECTED:
 * - Complex 3D layered system with multiple Z positions
 * - BoxGeometry instead of PlaneGeometry 
 * - Complex rotations and scaling effects
 * - Higher opacity and thickness changes
 * 
 * CURRENT STATE: Working holographic dashboard with dynamic top section and clean middle section.
 * Template now properly loads without Django navigation interference.
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
        
        // Create middle section with Chart.js (Option 2)
        this.createMiddleSection();
        
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
            const chartStep = 25;
            switch(event.key.toLowerCase()) {
                case 'w': this.camera.position.y += step; break;
                case 's': this.camera.position.y -= step; break;
                case 'a': this.camera.position.x -= step; break;
                case 'd': this.camera.position.x += step; break;
                case 'q': this.camera.position.z += step; break;
                case 'e': this.camera.position.z -= step; break;
                case 'r': this.camera.position.set(0, 0, 550); break;
                // Chart positioning controls
                case 'arrowup': 
                    if (this.chartObject) {
                        this.chartObject.position.y += chartStep;
                        console.log('Chart Y position:', this.chartObject.position.y);
                    }
                    break;
                case 'arrowdown':
                    if (this.chartObject) {
                        this.chartObject.position.y -= chartStep;
                        console.log('Chart Y position:', this.chartObject.position.y);
                    }
                    break;
                case 'arrowleft':
                    if (this.chartObject) {
                        this.chartObject.position.x -= chartStep;
                        console.log('Chart X position:', this.chartObject.position.x);
                    }
                    break;
                case 'arrowright':
                    if (this.chartObject) {
                        this.chartObject.position.x += chartStep;
                        console.log('Chart X position:', this.chartObject.position.x);
                    }
                    break;
                case ' ': 
                    event.preventDefault();
                    console.log('Current camera position:', this.camera.position);
                    if (this.chartObject) {
                        console.log('Current chart position:', this.chartObject.position);
                    }
                    break;
            }
            this.camera.lookAt(0, 0, 0);
            this.updatePositionDisplay();
        });
    }
    
    updatePositionDisplay() {
        const display = document.getElementById('camera-position');
        if (display) {
            const chartPos = this.chartObject ? this.chartObject.position : { x: 'N/A', y: 'N/A' };
            display.innerHTML = `
                Camera: x=${Math.round(this.camera.position.x)}, y=${Math.round(this.camera.position.y)}, z=${Math.round(this.camera.position.z)}<br>
                Chart: x=${Math.round(chartPos.x)}, y=${Math.round(chartPos.y)}<br>
                <strong>Controls:</strong><br>
                WASD: Move camera<br>
                Arrow Keys: Move chart<br>
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
        
        // Animate growing fault duration line
        this.animateFaultDurationLine();
        
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
    
    animateFaultDurationLine() {
        if (this.faultDurationLine && this.faultStartTime) {
            const currentTime = Date.now();
            const elapsedSeconds = (currentTime - this.faultStartTime) / 1000;
            
            // Simulate 10 minutes downtime, growing the line over 10 seconds for demo
            const maxDurationSeconds = 10; // 10 second demo cycle
            const progressPercent = Math.min((elapsedSeconds % maxDurationSeconds) / maxDurationSeconds * 100, 100);
            
            this.faultDurationLine.style.width = progressPercent + '%';
            
            // Add pulsing glow effect when line is growing
            if (progressPercent < 100) {
                const pulseIntensity = Math.sin(elapsedSeconds * 3) * 0.5 + 0.5;
                this.faultDurationLine.style.boxShadow = `0 0 ${10 + pulseIntensity * 15}px #00ffff`;
            }
        }
    }
    
    createMiddleSection() {
        // Chart section positioned in middle of screen
        const chartGroup = new THREE.Group();
        
        // Chart container positioned on left side (69% larger total)
        const chartWidth = 676;  // 520 * 1.3
        const chartHeight = 338; // 260 * 1.3
        const chartX = -150; // Optimized position
        const chartY = -25;  // Optimized position
        
        // Create chart container with enhanced size enforcement (Solution 2)
        const chartContainer = document.createElement('div');
        chartContainer.style.width = chartWidth + 'px';
        chartContainer.style.height = chartHeight + 'px';
        chartContainer.style.backgroundColor = 'transparent';
        chartContainer.style.border = 'none';
        chartContainer.style.borderRadius = '0';
        chartContainer.style.padding = '15px';
        chartContainer.style.boxSizing = 'border-box';
        chartContainer.style.position = 'relative';
        chartContainer.style.overflow = 'hidden';
        chartContainer.style.maxWidth = chartWidth + 'px';
        chartContainer.style.maxHeight = chartHeight + 'px';
        chartContainer.style.minWidth = chartWidth + 'px';
        chartContainer.style.minHeight = chartHeight + 'px';
        chartContainer.style.display = 'block';
        chartContainer.style.flex = 'none';
        chartContainer.style.transform = 'none';
        chartContainer.style.zIndex = '1';
        
        // Create canvas for Chart.js with explicit size constraints
        const canvas = document.createElement('canvas');
        canvas.id = 'plannedActualChart';
        canvas.width = 625;  // 481 * 1.3
        canvas.height = 287;  // 221 * 1.3
        canvas.style.width = '625px';  // Fixed display size
        canvas.style.height = '287px';
        canvas.style.maxWidth = '625px';
        canvas.style.maxHeight = '287px';
        chartContainer.appendChild(canvas);
        
        // Create Chart.js chart with responsive disabled
        const ctx = canvas.getContext('2d');
        const chart = new window.Chart(ctx, {
            type: 'line',
            data: {
                labels: ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '24:00'],
                datasets: [
                    {
                        label: 'Planned',
                        data: [100, 110, 120, 130, 125, 115, 105],
                        borderColor: '#00ffff',
                        backgroundColor: 'rgba(0, 255, 255, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.1
                    },
                    {
                        label: 'Actual',
                        data: [98, 108, 118, 128, 122, 112, 102],
                        borderColor: '#ffffff',
                        backgroundColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.1
                    }
                ]
            },
            plugins: [{
                id: 'downtimeHotSpots',
                afterDatasetsDraw: function(chart) {
                    const ctx = chart.ctx;
                    const chartArea = chart.chartArea;
                    
                    // Define downtime events
                    const downtimeEvents = [
                        { timeIndex: 2.3, severity: 'high' },   // Around 08:00-12:00
                        { timeIndex: 4.7, severity: 'medium' }  // Around 16:00-20:00
                    ];
                    
                    // Draw downtime hot spots
                    downtimeEvents.forEach(event => {
                        const xPosition = chartArea.left + (event.timeIndex / 6) * (chartArea.right - chartArea.left);
                        const yPosition = chartArea.top + (chartArea.bottom - chartArea.top) * 0.5;
                        
                        const hotSpotColor = event.severity === 'high' ? '#ff4444' : '#ff8844';
                        
                        // Create layered glow effect
                        ctx.save();
                        for (let i = 3; i >= 1; i--) {
                            ctx.shadowColor = hotSpotColor;
                            ctx.shadowBlur = i * 8;
                            ctx.globalAlpha = 0.4 / i;
                            ctx.fillStyle = hotSpotColor;
                            ctx.beginPath();
                            ctx.arc(xPosition, yPosition, i * 3, 0, Math.PI * 2);
                            ctx.fill();
                        }
                        ctx.restore();
                    });
                    
                    // Draw current time "NOW" line
                    const currentTimeIndex = 3.5; // Around 14:00 (current time)
                    const nowX = chartArea.left + (currentTimeIndex / 6) * (chartArea.right - chartArea.left);
                    
                    // Draw dashed vertical line
                    ctx.save();
                    ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)';
                    ctx.lineWidth = 2;
                    ctx.setLineDash([5, 5]);
                    ctx.beginPath();
                    ctx.moveTo(nowX, chartArea.top);
                    ctx.lineTo(nowX, chartArea.bottom);
                    ctx.stroke();
                    ctx.setLineDash([]);
                    
                    // Draw NOW label
                    ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
                    ctx.font = '10px system-ui';
                    ctx.textAlign = 'center';
                    ctx.fillText('NOW', nowX, chartArea.top - 8);
                    ctx.restore();
                }
            }],
            options: {
                responsive: false,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Planned vs Actual Performance',
                        color: 'rgba(0, 255, 255, 0.7)',
                        font: {
                            size: 14,
                            weight: 'bold'
                        }
                    },
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: {
                            color: 'rgba(255, 255, 255, 0.7)',
                            font: {
                                size: 10
                            },
                            filter: function(legendItem) {
                                return legendItem.text === 'Planned' || legendItem.text === 'Actual';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(0, 255, 255, 0.1)',
                            lineWidth: 1
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.5)',
                            font: {
                                size: 10
                            }
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(0, 255, 255, 0.1)',
                            lineWidth: 1
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.5)',
                            font: {
                                size: 9
                            }
                        }
                    }
                },
                elements: {
                    point: {
                        radius: 3,
                        hoverRadius: 5
                    }
                }
            }
        });
        
        const chartObject = new CSS2DObject(chartContainer);
        chartObject.position.set(chartX, chartY, 0);
        chartObject.center.set(0.5, 0.5);
        chartGroup.add(chartObject);
        
        // Store chart object for positioning controls
        this.chartObject = chartObject;
        
        // Add right side cards
        this.createRightSideCards(chartGroup);
        
        this.scene.add(chartGroup);
    }
    
    createRightSideCards(chartGroup) {
        const cardWidth = 300;
        const cardHeight = 160;
        const cardSpacing = 140;
        const rightX = 380; // Right side of middle section
        
        // Active Fault Overlay Card (top)
        this.createActiveFaultCard(chartGroup, cardWidth, cardHeight, rightX, 60);
        
        // Last Downtime Event Card (bottom)
        this.createLastDowntimeCard(chartGroup, cardWidth, cardHeight, rightX, -110);
    }
    
    createActiveFaultCard(chartGroup, width, height, x, y) {
        const faultDiv = document.createElement('div');
        faultDiv.style.width = width + 'px';
        faultDiv.style.height = height + 'px';
        faultDiv.style.backgroundColor = 'transparent';
        faultDiv.style.border = 'none';
        faultDiv.style.borderRadius = '0';
        faultDiv.style.padding = '15px';
        faultDiv.style.boxSizing = 'border-box';
        faultDiv.style.display = 'flex';
        faultDiv.style.flexDirection = 'column';
        
        // Header
        const header = document.createElement('div');
        header.style.color = '#00ffff';
        header.style.fontSize = '12px';
        header.style.fontWeight = '600';
        header.style.textTransform = 'uppercase';
        header.style.letterSpacing = '1px';
        header.style.marginBottom = '12px';
        header.textContent = 'Active Fault Overlay';
        
        // Machine name that caused the fault
        const machineName = document.createElement('div');
        machineName.style.color = '#ffffff';
        machineName.style.fontSize = '14px';
        machineName.style.fontWeight = '700';
        machineName.style.marginBottom = '8px';
        machineName.style.textShadow = '0 0 8px #00ffff';
        machineName.textContent = 'Machine: PRESS-001';
        
        // Growing line container representing downtime duration
        const downtimeLineContainer = document.createElement('div');
        downtimeLineContainer.style.width = '100%';
        downtimeLineContainer.style.height = '6px';
        downtimeLineContainer.style.backgroundColor = 'rgba(0, 255, 255, 0.1)';
        downtimeLineContainer.style.borderRadius = '3px';
        downtimeLineContainer.style.marginBottom = '12px';
        downtimeLineContainer.style.position = 'relative';
        downtimeLineContainer.style.overflow = 'hidden';
        
        // Growing line bar
        const growingLine = document.createElement('div');
        growingLine.style.height = '100%';
        growingLine.style.backgroundColor = '#00ffff';
        growingLine.style.borderRadius = '3px';
        growingLine.style.boxShadow = '0 0 10px #00ffff';
        growingLine.style.transition = 'width 1s ease-out';
        growingLine.style.width = '0%';
        growingLine.id = 'fault-duration-line';
        
        downtimeLineContainer.appendChild(growingLine);
        
        // MTTR/MTBF columns
        const metricsContainer = document.createElement('div');
        metricsContainer.style.display = 'flex';
        metricsContainer.style.justifyContent = 'space-between';
        
        // MTTR column
        const mttrColumn = document.createElement('div');
        mttrColumn.style.textAlign = 'center';
        mttrColumn.innerHTML = `
            <div style="color: #00ffff; font-size: 10px; font-weight: 600; margin-bottom: 4px;">MTTR</div>
            <div style="color: #ffffff; font-size: 16px; font-weight: 700;">8.2</div>
            <div style="color: rgba(255,255,255,0.6); font-size: 9px;">minutes</div>
        `;
        
        // MTBF column
        const mtbfColumn = document.createElement('div');
        mtbfColumn.style.textAlign = 'center';
        mtbfColumn.innerHTML = `
            <div style="color: #00ffff; font-size: 10px; font-weight: 600; margin-bottom: 4px;">MTBF</div>
            <div style="color: #ffffff; font-size: 16px; font-weight: 700;">142</div>
            <div style="color: rgba(255,255,255,0.6); font-size: 9px;">hours</div>
        `;
        
        metricsContainer.appendChild(mttrColumn);
        metricsContainer.appendChild(mtbfColumn);
        
        faultDiv.appendChild(header);
        faultDiv.appendChild(machineName);
        faultDiv.appendChild(downtimeLineContainer);
        faultDiv.appendChild(metricsContainer);
        
        const faultObject = new CSS2DObject(faultDiv);
        faultObject.position.set(x, y, 0);
        faultObject.center.set(0.5, 0.5);
        chartGroup.add(faultObject);
        
        // Store reference for growing line animation
        this.faultDurationLine = growingLine;
        this.faultStartTime = Date.now();
    }
    
    createLastDowntimeCard(chartGroup, width, height, x, y) {
        const downtimeDiv = document.createElement('div');
        downtimeDiv.style.width = width + 'px';
        downtimeDiv.style.height = height + 'px';
        downtimeDiv.style.backgroundColor = 'transparent';
        downtimeDiv.style.border = 'none';
        downtimeDiv.style.borderRadius = '0';
        downtimeDiv.style.padding = '15px';
        downtimeDiv.style.boxSizing = 'border-box';
        downtimeDiv.style.display = 'flex';
        downtimeDiv.style.flexDirection = 'column';
        
        // Header
        const header = document.createElement('div');
        header.style.color = '#00ffff';
        header.style.fontSize = '12px';
        header.style.fontWeight = '600';
        header.style.textTransform = 'uppercase';
        header.style.letterSpacing = '1px';
        header.style.marginBottom = '12px';
        header.textContent = 'Last Downtime Event';
        
        // Fault details
        const faultDetails = document.createElement('div');
        faultDetails.style.display = 'flex';
        faultDetails.style.flexDirection = 'column';
        faultDetails.style.gap = '8px';
        
        // Fault name
        const faultNameDiv = document.createElement('div');
        faultNameDiv.style.color = '#ffffff';
        faultNameDiv.style.fontSize = '11px';
        faultNameDiv.innerHTML = '<strong>Fault:</strong> Conveyor Belt Jam';
        
        // Duration
        const durationDiv = document.createElement('div');
        durationDiv.style.color = '#ffffff';
        durationDiv.style.fontSize = '11px';
        durationDiv.innerHTML = '<strong>Duration:</strong> 12.5 minutes';
        
        // Time occurred
        const timeDiv = document.createElement('div');
        timeDiv.style.color = 'rgba(255, 255, 255, 0.7)';
        timeDiv.style.fontSize = '10px';
        timeDiv.innerHTML = '<strong>Time:</strong> 13:45:22';
        
        faultDetails.appendChild(faultNameDiv);
        faultDetails.appendChild(durationDiv);
        faultDetails.appendChild(timeDiv);
        
        downtimeDiv.appendChild(header);
        downtimeDiv.appendChild(faultDetails);
        
        const downtimeObject = new CSS2DObject(downtimeDiv);
        downtimeObject.position.set(x, y, 0);
        downtimeObject.center.set(0.5, 0.5);
        chartGroup.add(downtimeObject);
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