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
        
        // Enable physically correct lighting for glass
        this.renderer.physicallyCorrectLights = true;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.0;
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        
        this.container.appendChild(this.renderer.domElement);
        
        // Setup CSS2D renderer for HTML overlays
        this.css2dRenderer = new CSS2DRenderer();
        this.css2dRenderer.setSize(window.innerWidth, window.innerHeight);
        this.css2dRenderer.domElement.style.position = 'absolute';
        this.css2dRenderer.domElement.style.top = '0px';
        this.css2dRenderer.domElement.style.pointerEvents = 'none';
        this.container.appendChild(this.css2dRenderer.domElement);
        
        // Add CSS for animations and effects
        this.injectHUDStyles();
        
        // Add grid background
        this.createGridBackground();
        
        // Create KPI cards with proper CSS2D positioning
        this.createKPICards();
        
        // Create middle section with Chart.js (Option 2)
        this.createMiddleSection();
        
        // Create bottom section with machine status and data readouts
        this.createBottomSection();
        
        // Add enhanced lighting for glass materials
        this.addGlassLighting();
        
        // Add environmental effects
        this.createIndividualScanLines();
        
        
        // Add reflection effects like Minority Report
        this.createReflectionEffects();
        
        // Phase 1: Add system status indicators (last so they're on top)
        setTimeout(() => {
            this.createSystemStatusIndicators();
        }, 100);
        
        // Start animation loop
        this.animate();
        
        // Setup resize and controls
        window.addEventListener('resize', () => this.onWindowResize());
        this.setupCameraControls();
    }
    
    createKPICards() {
        const cardData = [
            { label: 'Availability', value: '95%', color: 0x00d4ff },
            { label: 'Performance', value: '88%', color: 0x00d4ff },
            { label: 'Quality', value: '98%', color: 0x00d4ff },
            { label: 'Overall OEE', value: '82%', color: 0x00d4ff }
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
        header.style.color = '#66ccff';
        header.style.fontSize = '12px';
        header.style.fontWeight = '600';
        header.style.textTransform = 'uppercase';
        header.style.letterSpacing = '1px';
        header.textContent = cardData.label;
        
        // Main value
        const value = document.createElement('div');
        value.style.color = '#00d4ff';
        value.style.fontSize = '3rem';
        value.style.fontWeight = '700';
        value.style.textAlign = 'center';
        value.style.textShadow = '0 0 15px #00d4ff';
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
    
    injectHUDStyles() {
        console.log('INJECTING HUD STYLES - Fighter Jet Mode Active');
        const style = document.createElement('style');
        style.textContent = `
            @keyframes pulseRed {
                0% { opacity: 0.4; }
                50% { opacity: 1; }
                100% { opacity: 0.4; }
            }
            
            @keyframes warningPulse {
                0% { transform: scale(1); }
                100% { transform: scale(1.2); }
            }
            
            @keyframes scanLine {
                0% { transform: translateY(-100%); }
                100% { transform: translateY(calc(100vh + 100%)); }
            }
            
            @keyframes dataStream {
                0% { transform: translateX(-100%); opacity: 0; }
                10% { opacity: 1; }
                90% { opacity: 1; }
                100% { transform: translateX(100%); opacity: 0; }
            }
            
            @keyframes typewriter {
                from { width: 0; }
                to { width: 200px; }
            }
            
            .military-panel::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(
                    135deg,
                    transparent 0%,
                    rgba(0, 255, 255, 0.05) 50%,
                    transparent 100%
                );
                pointer-events: none;
            }
            
            
            .data-callout {
                position: absolute;
                background: rgba(0, 20, 0, 0.9);
                border: 1px solid #00d4ff;
                padding: 5px 10px;
                color: #00d4ff;
                font-family: 'Courier New', monospace;
                font-size: 10px;
                white-space: nowrap;
                z-index: 1000;
                pointer-events: none;
            }
            
            .leader-line {
                position: absolute;
                height: 1px;
                background: #00d4ff;
                transform-origin: left center;
                pointer-events: none;
            }
            
            .info-typewriter {
                overflow: hidden;
                white-space: nowrap;
                width: 0;
                max-width: 200px;
                animation: typewriter 2s steps(40) 1s normal both;
            }
            
            /* Phase 1: System Status Indicators */
            .system-status-panel {
                position: fixed;
                background: rgba(0, 20, 20, 0.9);
                border: 1px solid #00d4ff;
                border-radius: 0;
                color: #00d4ff;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                padding: 10px;
                z-index: 1005;
                backdrop-filter: blur(2px);
            }
            
            .status-indicator {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin: 3px 0;
                padding: 2px 0;
            }
            
            .status-light {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                margin-left: 8px;
            }
            
            .status-green { background: #00ff00; box-shadow: 0 0 8px #00ff00; }
            .status-yellow { background: #ffff00; box-shadow: 0 0 8px #ffff00; animation: pulseYellow 2s infinite; }
            .status-red { background: #ff4444; box-shadow: 0 0 8px #ff4444; animation: pulseRed 1s infinite; }
            
            @keyframes pulseYellow {
                0% { opacity: 0.6; }
                50% { opacity: 1; }
                100% { opacity: 0.6; }
            }
            
            .progress-bar {
                width: 60px;
                height: 8px;
                background: rgba(0, 255, 255, 0.2);
                border: 1px solid #00d4ff;
                position: relative;
                overflow: hidden;
            }
            
            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #00d4ff, #00aaaa);
                transition: width 0.5s ease;
                box-shadow: 0 0 6px #00d4ff;
            }
            
            .signal-bars {
                display: flex;
                gap: 2px;
                align-items: flex-end;
            }
            
            .signal-bar {
                width: 3px;
                background: #00d4ff;
                box-shadow: 0 0 4px #00d4ff;
            }
            
            /* Phase 2: Holographic Distortion Effects */
            @keyframes holographicShimmer {
                0% { background-position: -100% 0; }
                100% { background-position: 100% 0; }
            }
            
            @keyframes chromaticShift {
                0% { filter: hue-rotate(0deg); }
                25% { filter: hue-rotate(2deg); }
                75% { filter: hue-rotate(-2deg); }
                100% { filter: hue-rotate(0deg); }
            }
            
            @keyframes interference {
                0% { opacity: 1; }
                92% { opacity: 1; }
                93% { opacity: 0.8; }
                94% { opacity: 1; }
                96% { opacity: 0.9; }
                97% { opacity: 1; }
                100% { opacity: 1; }
            }
            
            @keyframes staticNoise {
                0% { transform: translateX(0) translateY(0); }
                10% { transform: translateX(-1px) translateY(1px); }
                20% { transform: translateX(1px) translateY(-1px); }
                30% { transform: translateX(-1px) translateY(-1px); }
                40% { transform: translateX(1px) translateY(1px); }
                50% { transform: translateX(0) translateY(-1px); }
                60% { transform: translateX(-1px) translateY(0); }
                70% { transform: translateX(1px) translateY(0); }
                80% { transform: translateX(0) translateY(1px); }
                90% { transform: translateX(-1px) translateY(-1px); }
                100% { transform: translateX(0) translateY(0); }
            }
            
            .holographic-element {
                position: relative;
            }
            
            
            .holographic-element::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(
                    90deg,
                    rgba(255, 0, 0, 0.02) 0%,
                    rgba(0, 255, 0, 0.02) 50%,
                    rgba(0, 0, 255, 0.02) 100%
                );
                animation: chromaticShift 4s ease-in-out infinite;
                pointer-events: none;
                mix-blend-mode: soft-light;
            }
            
            .interference-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: 
                    repeating-linear-gradient(
                        0deg,
                        transparent,
                        transparent 2px,
                        rgba(0, 255, 255, 0.01) 2px,
                        rgba(0, 255, 255, 0.01) 4px
                    );
                animation: interference 8s infinite;
                pointer-events: none;
                z-index: 500;
                mix-blend-mode: overlay;
            }
            
            .depth-blur {
                filter: blur(0.5px);
                opacity: 0.7;
            }
            
            /* Phase 3: Hexagonal Pattern System */
            .hexagonal-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background-image: 
                    radial-gradient(circle at 50px 50px, rgba(0, 212, 255, 0.1) 2px, transparent 2px);
                background-size: 100px 87px;
                background-position: 0 0, 50px 43px;
                pointer-events: none;
                z-index: 1;
                opacity: 0.3;
            }
            
            .hex-container {
                clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
                background: rgba(0, 255, 255, 0.05);
                border: 1px solid #00d4ff;
                position: relative;
            }
            
            .hex-ripple {
                position: absolute;
                border: 2px solid #00d4ff;
                border-radius: 50%;
                pointer-events: none;
            }
            
            @keyframes hexRipple {
                0% {
                    transform: scale(0);
                    opacity: 1;
                }
                100% {
                    transform: scale(4);
                    opacity: 0;
                }
            }
            
            @keyframes tessellate {
                0% { background-position: 0 0, 50px 43px; }
                100% { background-position: 100px 87px, 150px 130px; }
            }
            
            .honeycomb-grid {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: 
                    linear-gradient(90deg, transparent 74%, rgba(0, 255, 255, 0.08) 75%, rgba(0, 255, 255, 0.08) 76%, transparent 77%),
                    linear-gradient(30deg, transparent 74%, rgba(0, 255, 255, 0.08) 75%, rgba(0, 255, 255, 0.08) 76%, transparent 77%),
                    linear-gradient(-30deg, transparent 74%, rgba(0, 255, 255, 0.08) 75%, rgba(0, 255, 255, 0.08) 76%, transparent 77%);
                background-size: 60px 104px;
                animation: tessellate 20s linear infinite;
                pointer-events: none;
                z-index: 2;
                opacity: 0.4;
            }
            
            /* Phase 4: Advanced Visual Effects */
            .particle-field {
                position: fixed;
                width: 6px;
                height: 6px;
                background: #00d4ff;
                border-radius: 50%;
                pointer-events: none;
                z-index: 1003;
                opacity: 1;
                box-shadow: 0 0 12px #00d4ff;
            }
            
            @keyframes floatParticle {
                0% { transform: translateY(0) scale(1); opacity: 1; }
                100% { transform: translateY(-100vh) scale(1); opacity: 0; }
            }
            
            .electromagnetic-field {
                position: absolute;
                border: 1px solid rgba(0, 255, 255, 0.3);
                border-radius: 50%;
                pointer-events: none;
            }
            
            @keyframes electromagnet {
                0% { transform: scale(1) rotate(0deg); opacity: 0.3; }
                50% { transform: scale(1.2) rotate(180deg); opacity: 0.6; }
                100% { transform: scale(1) rotate(360deg); opacity: 0.3; }
            }
            
            .edge-glow {
                position: relative;
            }
            
            .edge-glow::before {
                content: '';
                position: absolute;
                top: -2px;
                left: -2px;
                right: -2px;
                bottom: -2px;
                background: linear-gradient(45deg, transparent, rgba(0, 255, 255, 0.4), transparent);
                border-radius: inherit;
                z-index: -1;
                animation: edgeGlow 3s ease-in-out infinite alternate;
                pointer-events: none;
            }
            
            @keyframes edgeGlow {
                0% { opacity: 0.2; transform: scale(1); }
                100% { opacity: 0.8; transform: scale(1.05); }
            }
            
            /* Minority Report Reflection Effects */
            .glass-reflection {
                position: relative;
                overflow: hidden;
            }
            
            .glass-reflection::before {
                content: '';
                position: absolute;
                top: 5%;
                left: 5%;
                width: 30%;
                height: 30%;
                background: linear-gradient(135deg, rgba(255, 255, 255, 0.8) 0%, rgba(255, 255, 255, 0.4) 50%, transparent 100%);
                border-radius: 50%;
                pointer-events: none;
                z-index: 10;
                animation: reflectionShimmer 4s ease-in-out infinite;
            }
            
            @keyframes reflectionShimmer {
                0% { opacity: 0.3; transform: scale(0.8) rotate(0deg); }
                50% { opacity: 0.8; transform: scale(1.2) rotate(180deg); }
                100% { opacity: 0.3; transform: scale(0.8) rotate(360deg); }
            }
            
            .surface-highlight {
                position: relative;
            }
            
            .surface-highlight::after {
                content: '';
                position: absolute;
                top: 10%;
                right: 15%;
                width: 25%;
                height: 25%;
                background: radial-gradient(ellipse at center, rgba(255, 255, 255, 0.6) 0%, rgba(255, 255, 255, 0.2) 40%, transparent 70%);
                pointer-events: none;
                z-index: 5;
                animation: highlightPulse 3s ease-in-out infinite alternate;
            }
            
            @keyframes highlightPulse {
                0% { opacity: 0.4; transform: scale(0.9); }
                100% { opacity: 0.8; transform: scale(1.1); }
            }
            
            /* Technical Background Pattern */
            .technical-background {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: 
                    /* Circuit traces */
                    linear-gradient(90deg, transparent 49%, rgba(0, 212, 255, 0.08) 50%, transparent 51%),
                    linear-gradient(0deg, transparent 49%, rgba(0, 212, 255, 0.08) 50%, transparent 51%),
                    /* Diagonal grid */
                    linear-gradient(45deg, transparent 48%, rgba(0, 212, 255, 0.05) 50%, transparent 52%),
                    linear-gradient(-45deg, transparent 48%, rgba(0, 212, 255, 0.05) 50%, transparent 52%),
                    /* Fine detail grid */
                    repeating-linear-gradient(0deg, transparent 0px, transparent 19px, rgba(0, 212, 255, 0.03) 20px),
                    repeating-linear-gradient(90deg, transparent 0px, transparent 19px, rgba(0, 212, 255, 0.03) 20px);
                background-size: 
                    200px 200px,
                    200px 200px,
                    100px 100px,
                    100px 100px,
                    20px 20px,
                    20px 20px;
                pointer-events: none;
                z-index: 1;
                opacity: 0.6;
            }
            
            .circuit-trace {
                position: absolute;
                height: 1px;
                background: linear-gradient(90deg, transparent, rgba(0, 212, 255, 0.4), transparent);
                pointer-events: none;
                animation: traceFlow 8s linear infinite;
            }
            
            @keyframes traceFlow {
                0% { width: 0; opacity: 0; }
                25% { opacity: 1; }
                75% { opacity: 1; }
                100% { width: 100%; opacity: 0; }
            }
            
            /* Minority Report Background Interface - Static, Deep, Blurred */
            .minority-report-bg {
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%) scale(1.4);
                width: 1600px;
                height: 1600px;
                pointer-events: none;
                z-index: 1;
                opacity: 0.08;
                filter: blur(1px);
            }
            
            .central-outer-ring {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 900px;
                height: 900px;
                border: 8px solid rgba(0, 212, 255, 0.4);
                border-radius: 50%;
            }
            
            .concentric-ring {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                border: 6px solid rgba(0, 212, 255, 0.2);
                border-radius: 50%;
            }
            
            .crosshair-lines {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 900px;
                height: 900px;
            }
            
            .crosshair-lines::before {
                content: '';
                position: absolute;
                top: 50%;
                left: 0;
                width: 100%;
                height: 6px;
                background: rgba(0, 212, 255, 0.3);
            }
            
            .crosshair-lines::after {
                content: '';
                position: absolute;
                left: 50%;
                top: 0;
                height: 100%;
                width: 6px;
                background: rgba(0, 212, 255, 0.3);
            }
            
            .radial-lines {
                position: absolute;
                top: 50%;
                left: 50%;
                width: 900px;
                height: 900px;
                transform: translate(-50%, -50%);
            }
            
            .radial-line {
                position: absolute;
                top: 50%;
                left: 50%;
                width: 4px;
                height: 450px;
                background: linear-gradient(to bottom, rgba(0, 212, 255, 0.15), transparent);
                transform-origin: center top;
            }
            
            .tick-marks {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 100%;
                height: 100%;
            }
            
            .tick-mark {
                position: absolute;
                top: 0;
                left: 50%;
                width: 4px;
                height: 15px;
                background: rgba(0, 212, 255, 0.2);
                transform-origin: center 450px;
            }
            
            .center-dot {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 12px;
                height: 12px;
                background: rgba(0, 212, 255, 0.6);
                border-radius: 50%;
                box-shadow: 0 0 10px rgba(0, 212, 255, 0.4);
            }
            
            /* Additional detail elements */
            .arc-segment {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                border: 8px solid rgba(0, 212, 255, 0.2);
                border-radius: 50%;
                border-top-color: transparent;
                border-right-color: transparent;
            }
            
            .grid-overlay {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 900px;
                height: 900px;
                background-image: 
                    repeating-linear-gradient(0deg, transparent, transparent 29px, rgba(0, 212, 255, 0.1) 30px),
                    repeating-linear-gradient(90deg, transparent, transparent 29px, rgba(0, 212, 255, 0.1) 30px);
                background-size: 30px 30px;
            }
            
            .inner-circle {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 100px;
                height: 100px;
                border: 1px solid rgba(0, 212, 255, 0.5);
                border-radius: 50%;
                background: radial-gradient(circle, rgba(0, 212, 255, 0.1) 0%, transparent 70%);
            }
            
            .data-point {
                position: absolute;
                width: 4px;
                height: 4px;
                background: rgba(0, 212, 255, 0.6);
                border-radius: 50%;
                box-shadow: 0 0 6px rgba(0, 212, 255, 0.4);
            }
            
            /* Additional complex elements */
            .sector-divider {
                position: absolute;
                top: 50%;
                left: 50%;
                width: 900px;
                height: 900px;
                transform: translate(-50%, -50%);
                border: 2px dashed rgba(0, 212, 255, 0.15);
                border-radius: 50%;
            }
            
            .quadrant-marker {
                position: absolute;
                width: 20px;
                height: 20px;
                background: transparent;
                border: 3px solid rgba(0, 212, 255, 0.3);
                transform: rotate(45deg);
            }
            
            .range-indicator {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                border: 1px solid rgba(0, 212, 255, 0.2);
                border-radius: 50%;
                border-style: dotted;
            }
            
            .corner-bracket {
                position: absolute;
                width: 50px;
                height: 50px;
                border: 3px solid rgba(0, 212, 255, 0.25);
            }
            
            .corner-bracket.top-left {
                top: 20%;
                left: 20%;
                border-right: none;
                border-bottom: none;
            }
            
            .corner-bracket.top-right {
                top: 20%;
                right: 20%;
                border-left: none;
                border-bottom: none;
            }
            
            .corner-bracket.bottom-left {
                bottom: 20%;
                left: 20%;
                border-right: none;
                border-top: none;
            }
            
            .corner-bracket.bottom-right {
                bottom: 20%;
                right: 20%;
                border-left: none;
                border-top: none;
            }
            
            .measurement-text {
                position: absolute;
                color: rgba(0, 212, 255, 0.4);
                font-family: 'Courier New', monospace;
                font-size: 10px;
                letter-spacing: 2px;
            }
            
            .orbital-ring {
                position: absolute;
                top: 50%;
                left: 50%;
                border: 2px solid rgba(0, 212, 255, 0.1);
                border-radius: 50%;
                transform: translate(-50%, -50%) rotateX(60deg);
            }
        `;
        document.head.appendChild(style);
    }
    
    createIndividualScanLines() {
        console.log('CREATING INDIVIDUAL SCAN LINES for chart and cards');
        
        // Add scan line CSS for individual elements
        const scanStyle = document.createElement('style');
        scanStyle.textContent = `
            .scan-target {
                position: relative;
                overflow: hidden;
            }
            
            .scan-target::after {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 2px;
                background: linear-gradient(90deg, transparent, rgba(0, 212, 255, 0.8), transparent);
                box-shadow: 0 0 10px rgba(0, 212, 255, 0.8);
                animation: scanLine 5s linear infinite;
                pointer-events: none;
                z-index: 10;
            }
        `;
        document.head.appendChild(scanStyle);
    }
    
    createSystemStatusIndicators() {
        console.log('CREATING SYSTEM STATUS INDICATORS - Military Systems Online');
        
        // Weapon Systems Panel (top-left)
        this.createWeaponSystemsPanel();
        
        // Engine Parameters Panel (top-right)
        this.createEngineParametersPanel();
        
        // Fuel/Power Panel (bottom-left)
        this.createFuelPowerPanel();
        
        // Communications Panel (bottom-right)
        this.createCommunicationsPanel();
    }
    
    createWeaponSystemsPanel() {
        const panel = document.createElement('div');
        panel.className = 'system-status-panel';
        panel.style.top = '80px';
        panel.style.left = '20px';
        panel.style.width = '180px';
        panel.id = 'weapon-systems-panel';
        
        panel.innerHTML = `
            <div style="border-bottom: 1px solid #00d4ff; margin-bottom: 8px; padding-bottom: 4px; font-weight: bold;">WEAPON SYSTEMS</div>
            <div class="status-indicator">
                <span>TARGET LOCK</span>
                <div class="status-light status-green"></div>
            </div>
            <div class="status-indicator">
                <span>RADAR ACTIVE</span>
                <div class="status-light status-green"></div>
            </div>
            <div class="status-indicator">
                <span>COUNTERMEASURES</span>
                <div class="status-light status-yellow"></div>
            </div>
            <div class="status-indicator">
                <span>AMMO: 847/1000</span>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 85%;"></div>
                </div>
            </div>
        `;
        
        document.body.appendChild(panel);
    }
    
    createEngineParametersPanel() {
        const panel = document.createElement('div');
        panel.className = 'system-status-panel';
        panel.style.top = '80px';
        panel.style.right = '20px';
        panel.style.width = '170px';
        panel.id = 'engine-parameters-panel';
        
        panel.innerHTML = `
            <div style="border-bottom: 1px solid #00d4ff; margin-bottom: 8px; padding-bottom: 4px; font-weight: bold;">ENGINE STATUS</div>
            <div class="status-indicator">
                <span>TEMP: 742°C</span>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 74%;"></div>
                </div>
            </div>
            <div class="status-indicator">
                <span>RPM: 8,450</span>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 82%;"></div>
                </div>
            </div>
            <div class="status-indicator">
                <span>THRUST: 95%</span>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 95%;"></div>
                </div>
            </div>
            <div class="status-indicator">
                <span>HYDRAULICS</span>
                <div class="status-light status-green"></div>
            </div>
        `;
        
        document.body.appendChild(panel);
    }
    
    createFuelPowerPanel() {
        const panel = document.createElement('div');
        panel.className = 'system-status-panel';
        panel.style.bottom = '20px';
        panel.style.left = '20px';
        panel.style.width = '160px';
        panel.id = 'fuel-power-panel';
        
        panel.innerHTML = `
            <div style="border-bottom: 1px solid #00d4ff; margin-bottom: 8px; padding-bottom: 4px; font-weight: bold;">FUEL/POWER</div>
            <div class="status-indicator">
                <span>FUEL: 68%</span>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 68%;"></div>
                </div>
            </div>
            <div class="status-indicator">
                <span>BATTERY: 92%</span>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 92%;"></div>
                </div>
            </div>
            <div class="status-indicator">
                <span>CONSUMPTION</span>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 45%;"></div>
                </div>
            </div>
            <div class="status-indicator">
                <span>GENERATOR</span>
                <div class="status-light status-green"></div>
            </div>
        `;
        
        document.body.appendChild(panel);
    }
    
    createCommunicationsPanel() {
        const panel = document.createElement('div');
        panel.className = 'system-status-panel';
        panel.style.bottom = '20px';
        panel.style.right = '20px';
        panel.style.width = '170px';
        panel.id = 'communications-panel';
        
        panel.innerHTML = `
            <div style="border-bottom: 1px solid #00d4ff; margin-bottom: 8px; padding-bottom: 4px; font-weight: bold;">COMMUNICATIONS</div>
            <div class="status-indicator">
                <span>SIGNAL STRENGTH</span>
                <div class="signal-bars">
                    <div class="signal-bar" style="height: 6px;"></div>
                    <div class="signal-bar" style="height: 10px;"></div>
                    <div class="signal-bar" style="height: 14px;"></div>
                    <div class="signal-bar" style="height: 18px;"></div>
                    <div class="signal-bar" style="height: 12px;"></div>
                </div>
            </div>
            <div class="status-indicator">
                <span>DATALINK</span>
                <div class="status-light status-green"></div>
            </div>
            <div class="status-indicator">
                <span>ENCRYPTION</span>
                <div class="status-light status-green"></div>
            </div>
            <div class="status-indicator">
                <span>FREQ: 251.7MHz</span>
                <div class="status-light status-yellow"></div>
            </div>
        `;
        
        document.body.appendChild(panel);
    }
    
    createHolographicDistortion() {
        console.log('CREATING HOLOGRAPHIC DISTORTION EFFECTS - Phase 2 Active');
        
        // Add global interference overlay
        this.createInterferenceOverlay();
        
        // Apply holographic effects to existing elements
        this.applyHolographicEffects();
        
        // Add chromatic aberration to text elements
        this.addChromaticAberration();
        
        // Apply depth blur to background elements
        this.applyDepthBlur();
    }
    
    createInterferenceOverlay() {
        const interferenceOverlay = document.createElement('div');
        interferenceOverlay.className = 'interference-overlay';
        interferenceOverlay.id = 'global-interference';
        document.body.appendChild(interferenceOverlay);
        
        // Add additional static noise overlay
        const noiseOverlay = document.createElement('div');
        noiseOverlay.style.position = 'fixed';
        noiseOverlay.style.top = '0';
        noiseOverlay.style.left = '0';
        noiseOverlay.style.right = '0';
        noiseOverlay.style.bottom = '0';
        noiseOverlay.style.background = `
            radial-gradient(circle at 25% 25%, rgba(0, 255, 255, 0.02) 0%, transparent 50%),
            radial-gradient(circle at 75% 75%, rgba(0, 255, 255, 0.02) 0%, transparent 50%)
        `;
        noiseOverlay.style.animation = 'staticNoise 0.1s infinite';
        noiseOverlay.style.pointerEvents = 'none';
        noiseOverlay.style.zIndex = '499';
        noiseOverlay.id = 'static-noise';
        document.body.appendChild(noiseOverlay);
    }
    
    applyHolographicEffects() {
        // Apply holographic effects after elements are created
        setTimeout(() => {
            const chartPanel = document.getElementById('main-chart-panel');
            if (chartPanel) {
                chartPanel.classList.add('holographic-element');
                console.log('Applied holographic effects to chart panel');
            } else {
                console.log('Chart panel not found for holographic effects');
            }
            
            const activeFault = document.getElementById('active-fault-card');
            if (activeFault) {
                activeFault.classList.add('holographic-element');
                console.log('Applied holographic effects to active fault card');
            }
        }, 500);
    }
    
    addChromaticAberration() {
        // Add chromatic aberration to KPI values
        const kpiValues = document.querySelectorAll('[style*="font-size: 3rem"]');
        kpiValues.forEach(value => {
            value.style.textShadow = `
                2px 0px 0px rgba(255, 0, 0, 0.3),
                -2px 0px 0px rgba(0, 0, 255, 0.3),
                0px 0px 15px #00d4ff
            `;
            value.style.animation = 'chromaticShift 6s ease-in-out infinite';
        });
        
        // Add chromatic aberration to panel headers
        const panelHeaders = document.querySelectorAll('.system-status-panel div:first-child');
        panelHeaders.forEach(header => {
            header.style.textShadow = `
                1px 0px 0px rgba(255, 0, 0, 0.2),
                -1px 0px 0px rgba(0, 0, 255, 0.2)
            `;
        });
    }
    
    applyDepthBlur() {
        // Apply depth blur to background grid
        setTimeout(() => {
            const cameraPosition = document.getElementById('camera-position');
            if (cameraPosition) {
                cameraPosition.classList.add('depth-blur');
            }
        }, 100);
    }
    
    createHexagonalPatterns() {
        console.log('CREATING HEXAGONAL PATTERN SYSTEM - Phase 3 Active');
        
        // Create honeycomb background grid
        this.createHoneycombGrid();
        
        // Convert some elements to hexagonal containers
        this.createHexagonalContainers();
        
        // Add expanding ripple effects
        this.setupHexagonalRipples();
    }
    
    createHoneycombGrid() {
        // Honeycomb grid disabled per user preference
        console.log('Honeycomb grid disabled');
    }
    
    createHexagonalContainers() {
        // Hexagonal containers disabled per user preference
        console.log('Hexagonal containers disabled');
    }
    
    setupHexagonalRipples() {
        // Add click ripple effects to hexagonal elements
        document.addEventListener('click', (event) => {
            this.createHexRipple(event.clientX, event.clientY);
        });
        
        // Add periodic automatic ripples near important elements
        setInterval(() => {
            const activeFault = document.getElementById('active-fault-card');
            if (activeFault) {
                const rect = activeFault.getBoundingClientRect();
                this.createHexRipple(
                    rect.left + rect.width / 2,
                    rect.top + rect.height / 2
                );
            }
        }, 8000);
    }
    
    createHexRipple(x, y) {
        const ripple = document.createElement('div');
        ripple.className = 'hex-ripple';
        ripple.style.left = (x - 20) + 'px';
        ripple.style.top = (y - 20) + 'px';
        ripple.style.width = '40px';
        ripple.style.height = '40px';
        ripple.style.animation = 'hexRipple 2s ease-out';
        ripple.style.zIndex = '1000';
        
        document.body.appendChild(ripple);
        
        // Remove after animation
        setTimeout(() => {
            ripple.remove();
        }, 2000);
    }
    
    createReflectionEffects() {
        console.log('CREATING MINORITY REPORT REFLECTION EFFECTS');
        
        // Don't apply glass reflection to system status panels - it might hide them
        // setTimeout(() => {
        //     const panels = document.querySelectorAll('.system-status-panel');
        //     panels.forEach(panel => {
        //         panel.classList.add('glass-reflection');
        //     });
        // }, 300);
        
        // Apply surface highlights to charts and cards
        setTimeout(() => {
            const surfaceElements = [
                document.getElementById('main-chart-panel'),
                document.getElementById('active-fault-card')
            ];
            
            surfaceElements.forEach(element => {
                if (element) {
                    element.classList.add('surface-highlight');
                }
            });
        }, 500);
    }
    
    animateBackgroundDial() {
        // Removed - no animation needed for static background
    }
    
    createMinorityReportBackground() {
        console.log('CREATING STATIC MINORITY REPORT BACKGROUND - Deep and Blurred - V2 with more elements', Date.now());
        
        // Create the main background container
        const bgContainer = document.createElement('div');
        bgContainer.className = 'minority-report-bg';
        bgContainer.id = 'minority-report-interface';
        
        // Outer ring
        const outerRing = document.createElement('div');
        outerRing.className = 'central-outer-ring';
        bgContainer.appendChild(outerRing);
        
        // Multiple concentric rings
        const ringRadii = [150, 250, 350, 450, 550, 650, 750];
        ringRadii.forEach(radius => {
            const ring = document.createElement('div');
            ring.className = 'concentric-ring';
            ring.style.width = radius + 'px';
            ring.style.height = radius + 'px';
            bgContainer.appendChild(ring);
        });
        
        // Crosshair lines
        const crosshair = document.createElement('div');
        crosshair.className = 'crosshair-lines';
        bgContainer.appendChild(crosshair);
        
        // Radial lines container
        const radialContainer = document.createElement('div');
        radialContainer.className = 'radial-lines';
        
        // Add 24 radial lines (every 15 degrees)
        for (let i = 0; i < 24; i++) {
            const radialLine = document.createElement('div');
            radialLine.className = 'radial-line';
            radialLine.style.transform = `rotate(${i * 15}deg)`;
            radialContainer.appendChild(radialLine);
        }
        bgContainer.appendChild(radialContainer);
        
        // Tick marks around the outer ring
        const tickContainer = document.createElement('div');
        tickContainer.className = 'tick-marks';
        
        // Add 72 tick marks (every 5 degrees)
        for (let i = 0; i < 72; i++) {
            const tick = document.createElement('div');
            tick.className = 'tick-mark';
            const isLargeTick = i % 6 === 0;
            tick.style.height = isLargeTick ? '15px' : '8px';
            tick.style.transform = `rotate(${i * 5}deg)`;
            tickContainer.appendChild(tick);
        }
        bgContainer.appendChild(tickContainer);
        
        // Grid overlay
        const gridOverlay = document.createElement('div');
        gridOverlay.className = 'grid-overlay';
        bgContainer.appendChild(gridOverlay);
        
        // Inner circle with glow
        const innerCircle = document.createElement('div');
        innerCircle.className = 'inner-circle';
        bgContainer.appendChild(innerCircle);
        
        // Arc segments (partial circles)
        for (let i = 0; i < 4; i++) {
            const arc = document.createElement('div');
            arc.className = 'arc-segment';
            arc.style.width = (300 + i * 100) + 'px';
            arc.style.height = (300 + i * 100) + 'px';
            arc.style.transform = `translate(-50%, -50%) rotate(${i * 45}deg)`;
            bgContainer.appendChild(arc);
        }
        
        // Add random data points around the circles
        for (let i = 0; i < 30; i++) {
            const angle = Math.random() * Math.PI * 2;
            const radius = 200 + Math.random() * 250;
            const dataPoint = document.createElement('div');
            dataPoint.className = 'data-point';
            dataPoint.style.left = (50 + Math.cos(angle) * radius / 16) + '%';
            dataPoint.style.top = (50 + Math.sin(angle) * radius / 16) + '%';
            bgContainer.appendChild(dataPoint);
        }
        
        // Add sector dividers (dashed circles)
        console.log('Adding sector dividers...');
        for (let i = 0; i < 3; i++) {
            const sectorDivider = document.createElement('div');
            sectorDivider.className = 'sector-divider';
            sectorDivider.style.width = (400 + i * 150) + 'px';
            sectorDivider.style.height = (400 + i * 150) + 'px';
            sectorDivider.style.transform = `translate(-50%, -50%) rotate(${i * 30}deg)`;
            bgContainer.appendChild(sectorDivider);
        }
        
        // Add quadrant markers at key positions
        const quadrantPositions = [
            { top: '25%', left: '25%' },
            { top: '25%', right: '25%' },
            { bottom: '25%', left: '25%' },
            { bottom: '25%', right: '25%' }
        ];
        
        quadrantPositions.forEach(pos => {
            const marker = document.createElement('div');
            marker.className = 'quadrant-marker';
            Object.assign(marker.style, pos);
            bgContainer.appendChild(marker);
        });
        
        // Add range indicators (dotted circles)
        [200, 400, 600].forEach(radius => {
            const rangeIndicator = document.createElement('div');
            rangeIndicator.className = 'range-indicator';
            rangeIndicator.style.width = radius + 'px';
            rangeIndicator.style.height = radius + 'px';
            bgContainer.appendChild(rangeIndicator);
        });
        
        // Add corner brackets
        ['top-left', 'top-right', 'bottom-left', 'bottom-right'].forEach(corner => {
            const bracket = document.createElement('div');
            bracket.className = `corner-bracket ${corner}`;
            bgContainer.appendChild(bracket);
        });
        
        // Add measurement text at various angles
        const measurements = ['090°', '180°', '270°', '360°'];
        measurements.forEach((text, index) => {
            const measureText = document.createElement('div');
            measureText.className = 'measurement-text';
            measureText.textContent = text;
            const angle = (index * 90) * Math.PI / 180;
            measureText.style.left = (50 + Math.cos(angle) * 35) + '%';
            measureText.style.top = (50 + Math.sin(angle) * 35) + '%';
            bgContainer.appendChild(measureText);
        });
        
        // Add orbital rings (3D effect)
        for (let i = 0; i < 2; i++) {
            const orbitalRing = document.createElement('div');
            orbitalRing.className = 'orbital-ring';
            orbitalRing.style.width = (500 + i * 200) + 'px';
            orbitalRing.style.height = (500 + i * 200) + 'px';
            orbitalRing.style.transform = `translate(-50%, -50%) rotateX(${60 + i * 30}deg)`;
            bgContainer.appendChild(orbitalRing);
        }
        
        // Center dot (last so it's on top)
        const centerDot = document.createElement('div');
        centerDot.className = 'center-dot';
        bgContainer.appendChild(centerDot);
        
        document.body.appendChild(bgContainer);
        console.log('Minority Report background added to DOM:', bgContainer);
        console.log('Total child elements:', bgContainer.children.length);
        console.log('Element classes in container:', Array.from(bgContainer.children).map(child => child.className));
        
        this.backgroundInterface = { container: bgContainer };
    }
    
    createTechnicalBackground() {
        console.log('CREATING TECHNICAL BACKGROUND - Minority Report Style');
        
        // Create the main technical background overlay
        const techBackground = document.createElement('div');
        techBackground.className = 'technical-background';
        techBackground.id = 'technical-background';
        document.body.appendChild(techBackground);
        
        // Add animated circuit traces
        this.createCircuitTraces();
    }
    
    createCircuitTraces() {
        // Create flowing circuit traces across the screen
        const tracePositions = [
            { top: '20%', left: '10%', width: '30%' },
            { top: '45%', left: '60%', width: '25%' },
            { top: '70%', left: '15%', width: '40%' },
            { top: '25%', right: '10%', width: '20%' },
            { top: '80%', right: '30%', width: '35%' }
        ];
        
        tracePositions.forEach((pos, index) => {
            setTimeout(() => {
                const trace = document.createElement('div');
                trace.className = 'circuit-trace';
                trace.style.top = pos.top;
                if (pos.left) trace.style.left = pos.left;
                if (pos.right) trace.style.right = pos.right;
                trace.style.maxWidth = pos.width;
                trace.style.animationDelay = (index * 1.5) + 's';
                trace.style.zIndex = '2';
                
                document.body.appendChild(trace);
            }, index * 400);
        });
    }
    
    createAdvancedVisualEffects() {
        console.log('CREATING ADVANCED VISUAL EFFECTS - Phase 4 Active');
        
        // Create floating particle system background
        this.createParticleSystem();
        
        // Add electromagnetic field visualizations
        this.createElectromagneticFields();
        
        // Apply edge glow to active elements
        this.applyEdgeGlow();
    }
    
    createParticleSystem() {
        // Create floating particles in background
        for (let i = 0; i < 15; i++) {
            setTimeout(() => {
                this.createFloatingParticle();
            }, i * 200);
        }
        
        // Continuously spawn new particles
        setInterval(() => {
            this.createFloatingParticle();
        }, 3000);
    }
    
    createFloatingParticle() {
        const particle = document.createElement('div');
        particle.className = 'particle-field';
        
        // Random horizontal position
        const startX = Math.random() * window.innerWidth;
        
        particle.style.left = startX + 'px';
        particle.style.top = window.innerHeight + 'px';
        particle.style.animation = `floatParticle ${8 + Math.random() * 4}s linear forwards`;
        particle.style.zIndex = '10';
        
        document.body.appendChild(particle);
        console.log('Created floating particle at', startX);
        
        // Remove after animation
        setTimeout(() => {
            if (particle.parentNode) {
                particle.remove();
            }
        }, 12000);
    }
    
    createElectromagneticFields() {
        // Add electromagnetic fields around system status panels
        setTimeout(() => {
            const panels = document.querySelectorAll('.system-status-panel');
            panels.forEach((panel, index) => {
                const field = document.createElement('div');
                field.className = 'electromagnetic-field';
                field.style.width = '120%';
                field.style.height = '120%';
                field.style.top = '-10%';
                field.style.left = '-10%';
                field.style.animation = `electromagnet ${4 + index}s linear infinite`;
                field.style.zIndex = '-1';
                
                panel.style.position = 'relative';
                panel.appendChild(field);
            });
        }, 300);
    }
    
    applyEdgeGlow() {
        // Apply edge glow to critical elements
        setTimeout(() => {
            const criticalElements = [
                document.getElementById('active-fault-card'),
                document.getElementById('weapon-systems-panel')
            ];
            
            criticalElements.forEach(element => {
                if (element) {
                    element.classList.add('edge-glow');
                }
            });
        }, 500);
    }
    
    
    createDataCallout(x, y, text, targetElement) {
        const callout = document.createElement('div');
        callout.className = 'data-callout info-typewriter';
        callout.textContent = text;
        callout.style.left = x + 'px';
        callout.style.top = y + 'px';
        
        // Create leader line
        const line = document.createElement('div');
        line.className = 'leader-line';
        
        // Calculate line angle and length
        const targetRect = targetElement.getBoundingClientRect();
        const dx = targetRect.left + targetRect.width / 2 - x;
        const dy = targetRect.top + targetRect.height / 2 - y;
        const length = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx) * 180 / Math.PI;
        
        line.style.width = length + 'px';
        line.style.left = x + 'px';
        line.style.top = y + 'px';
        line.style.transform = `rotate(${angle}deg)`;
        
        document.body.appendChild(line);
        document.body.appendChild(callout);
        
        return { callout, line };
    }
    
    addInitialCallouts() {
        // Add callouts for chart
        const chartCallout = this.createDataCallout(
            window.innerWidth * 0.3, 
            window.innerHeight * 0.4, 
            'PERFORMANCE TRACKING ACTIVE',
            document.getElementById('main-chart-panel')
        );
        
        // Add callout for active fault
        const faultCallout = this.createDataCallout(
            window.innerWidth * 0.85, 
            window.innerHeight * 0.25, 
            'FAULT SYSTEM ONLINE',
            document.getElementById('active-fault-card')
        );
        
        // Store callouts for cleanup
        this.activeCallouts = [chartCallout, faultCallout];
    }
    
    triggerAlertState(severity = 'high') {
        const activeFaultCard = document.getElementById('active-fault-card');
        const warningIndicator = activeFaultCard.querySelector('.warning-indicator');
        
        if (severity === 'high') {
            // Flash red overlay
            const alertOverlay = document.createElement('div');
            alertOverlay.style.position = 'absolute';
            alertOverlay.style.top = '0';
            alertOverlay.style.left = '0';
            alertOverlay.style.right = '0';
            alertOverlay.style.bottom = '0';
            alertOverlay.style.backgroundColor = 'rgba(255, 68, 68, 0.3)';
            alertOverlay.style.pointerEvents = 'none';
            alertOverlay.style.animation = 'pulseRed 0.5s infinite';
            activeFaultCard.appendChild(alertOverlay);
            
            // Enhance warning triangle
            if (warningIndicator) {
                warningIndicator.style.animation = 'warningPulse 0.3s infinite alternate';
                warningIndicator.style.color = '#ff4444';
            }
            
            // Remove after 5 seconds
            setTimeout(() => {
                alertOverlay.remove();
                if (warningIndicator) {
                    warningIndicator.style.animation = 'warningPulse 0.5s infinite alternate';
                }
            }, 5000);
        }
    }
    
    setupCameraControls() {
        // Camera position display
        const positionDisplay = document.createElement('div');
        positionDisplay.id = 'camera-position';
        positionDisplay.style.position = 'fixed';
        positionDisplay.style.top = '10px';
        positionDisplay.style.left = '10px';
        positionDisplay.style.background = 'rgba(0,0,0,0.8)';
        positionDisplay.style.color = '#00d4ff';
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
        
        
        // Trigger periodic alert demonstrations
        this.handlePeriodicAlerts();
        
        // Animate system status indicators
        this.animateSystemStatus();
        
        // Animate machine sprockets based on status
        this.animateMachineSprockets();
        
        // Render both WebGL and CSS2D
        this.renderer.render(this.scene, this.camera);
        this.css2dRenderer.render(this.scene, this.camera);
    }
    
    
    handlePeriodicAlerts() {
        const time = Date.now() * 0.001;
        
        // Trigger demo alert every 15 seconds
        if (Math.floor(time) % 15 === 0 && Math.floor(time * 10) % 10 === 0) {
            this.triggerAlertState('high');
        }
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
                this.faultDurationLine.style.boxShadow = `0 0 ${10 + pulseIntensity * 15}px #00d4ff`;
            }
        }
    }
    
    animateSystemStatus() {
        const time = Date.now() * 0.001;
        
        // Animate engine parameters
        const enginePanel = document.getElementById('engine-parameters-panel');
        if (enginePanel) {
            const tempBar = enginePanel.querySelector('.status-indicator:nth-child(2) .progress-fill');
            const rpmBar = enginePanel.querySelector('.status-indicator:nth-child(3) .progress-fill');
            const thrustBar = enginePanel.querySelector('.status-indicator:nth-child(4) .progress-fill');
            
            if (tempBar) {
                const tempVariation = Math.sin(time * 0.5) * 5 + 74; // 69-79%
                tempBar.style.width = tempVariation + '%';
                tempBar.parentElement.previousElementSibling.innerHTML = `TEMP: ${Math.round(tempVariation * 10)}°C`;
            }
            
            if (rpmBar) {
                const rpmVariation = Math.sin(time * 0.3) * 3 + 82; // 79-85%
                rpmBar.style.width = rpmVariation + '%';
                const rpmValue = Math.round(rpmVariation * 100 + 400);
                rpmBar.parentElement.previousElementSibling.innerHTML = `RPM: ${rpmValue.toLocaleString()}`;
            }
            
            if (thrustBar) {
                const thrustVariation = Math.sin(time * 0.7) * 5 + 95; // 90-100%
                thrustBar.style.width = Math.min(100, thrustVariation) + '%';
            }
        }
        
        // Animate fuel consumption
        const fuelPanel = document.getElementById('fuel-power-panel');
        if (fuelPanel) {
            const fuelBar = fuelPanel.querySelector('.status-indicator:nth-child(2) .progress-fill');
            const consumptionBar = fuelPanel.querySelector('.status-indicator:nth-child(4) .progress-fill');
            
            if (fuelBar) {
                const fuelDepletion = Math.max(50, 68 - (time * 0.1)); // Slowly decreasing
                fuelBar.style.width = fuelDepletion + '%';
                fuelBar.parentElement.previousElementSibling.innerHTML = `FUEL: ${Math.round(fuelDepletion)}%`;
            }
            
            if (consumptionBar) {
                const consumption = Math.sin(time * 1.2) * 15 + 45; // 30-60%
                consumptionBar.style.width = consumption + '%';
            }
        }
        
        // Animate communication signal bars
        const commPanel = document.getElementById('communications-panel');
        if (commPanel) {
            const signalBars = commPanel.querySelectorAll('.signal-bar');
            signalBars.forEach((bar, index) => {
                const baseHeight = [6, 10, 14, 18, 12][index];
                const variation = Math.sin(time * (2 + index * 0.3)) * 3;
                bar.style.height = Math.max(3, baseHeight + variation) + 'px';
            });
        }
    }
    
    createMiddleSection() {
        // Chart section positioned in middle of screen
        const chartGroup = new THREE.Group();
        
        // Chart container positioned on left side (69% larger total, then 15% larger)
        const chartWidth = 777;  // 676 * 1.15
        const chartHeight = 389; // 338 * 1.15
        const chartX = -150; // Optimized position
        const chartY = -10;  // Moved up by 15 pixels: -25 + 15 = -10
        
        // Create chart container with military HUD styling
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
        chartContainer.className = 'scan-target';
        chartContainer.id = 'main-chart-panel';
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
        console.log('CREATING CHART.JS WITH HUD STYLING');
        const ctx = canvas.getContext('2d');
        const chart = new window.Chart(ctx, {
            type: 'line',
            data: {
                labels: ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '24:00'],
                datasets: [
                    {
                        label: 'Planned',
                        data: [100, 110, 120, 130, 125, 115, 105],
                        borderColor: '#66ccff',
                        backgroundColor: 'rgba(0, 102, 255, 0.1)',
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
                        color: 'rgba(255, 102, 0, 0.7)',
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
                            color: 'rgba(0, 212, 255, 0.1)',
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
                            color: 'rgba(0, 212, 255, 0.1)',
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
    
    createBottomSection() {
        console.log('CREATING BOTTOM SECTION - Machine Status and Data Readouts');
        
        const bottomGroup = new THREE.Group();
        
        // Position bottom section at bottom of screen
        const bottomY = -window.innerHeight * 0.35;
        bottomGroup.position.set(0, bottomY, 0);
        
        // Add two cards above sprockets
        this.createSprocketOverlayCards(bottomGroup);
        
        // Create machine status circles (left side)
        this.createMachineStatusCircles(bottomGroup);
        
        // Data readouts will appear only for faulted machines
        
        this.scene.add(bottomGroup);
    }
    
    createMachineStatusCircles(bottomGroup) {
        // Calculate machine statuses based on production flow (left to right)
        const baseMachineStatuses = [
            { id: 'M001', status: 'operational', name: 'CNC Lathe #1' },
            { id: 'M002', status: 'operational', name: 'Mill #3' },
            { id: 'M003', status: 'operational', name: 'Assembly #2' },
            { id: 'M004', status: 'fault', name: 'Press #1' },
            { id: 'M005', status: 'operational', name: 'Conveyor #4' },
            { id: 'M006', status: 'operational', name: 'Robot #2' },
            { id: 'M007', status: 'operational', name: 'Packaging #1' },
            { id: 'M008', status: 'operational', name: 'Sorter #3' },
            { id: 'M009', status: 'operational', name: 'Welder #2' },
            { id: 'M010', status: 'operational', name: 'Inspection #1' },
            { id: 'M011', status: 'operational', name: 'Palletizer #1' },
            { id: 'M012', status: 'operational', name: 'Wrapper #2' }
        ];
        
        // Apply starved status to machines downstream of faulted machines
        const machineStatuses = this.calculateProductionFlowStatus(baseMachineStatuses);
        
        const circleRadius = 20;
        const spacing = 80;
        const startX = -440;
        
        machineStatuses.forEach((machine, index) => {
            const circleGroup = new THREE.Group();
            
            // Create glass sprocket geometry
            const sprocketGeometry = this.createSprocketGeometry(circleRadius);
            let glassMaterial;
            
            if (machine.status === 'fault') {
                // Ultra-realistic red glass for stopped/fault machines
                glassMaterial = new THREE.MeshPhysicalMaterial({
                    transmission: 1.0,
                    opacity: 1.0,
                    thickness: 8,
                    roughness: 0,
                    ior: 1.52,
                    clearcoat: 1.0,
                    clearcoatRoughness: 0,
                    reflectivity: 0.9,
                    metalness: 0,
                    color: 0xffffff,
                    attenuationColor: 0xff0000,
                    attenuationDistance: 0.2,
                    transparent: false,
                    side: THREE.DoubleSide
                });
            } else if (machine.status === 'starved') {
                // Ultra-realistic grey glass for starved machines
                glassMaterial = new THREE.MeshPhysicalMaterial({
                    transmission: 0.8,
                    opacity: 1.0,
                    thickness: 8,
                    roughness: 0,
                    ior: 1.52,
                    clearcoat: 1.0,
                    clearcoatRoughness: 0,
                    reflectivity: 0.9,
                    metalness: 0,
                    color: 0xffffff,
                    attenuationColor: 0x808080,
                    attenuationDistance: 0.2,
                    transparent: false,
                    side: THREE.DoubleSide
                });
            } else {
                // Ultra-realistic green glass for operational machines  
                glassMaterial = new THREE.MeshPhysicalMaterial({
                    transmission: 1.0,
                    opacity: 1.0,
                    thickness: 8,
                    roughness: 0,
                    ior: 1.52,
                    clearcoat: 1.0,
                    clearcoatRoughness: 0,
                    reflectivity: 0.9,
                    metalness: 0,
                    color: 0xffffff,
                    attenuationColor: 0x00ff00,
                    attenuationDistance: 0.3,
                    transparent: false,
                    side: THREE.DoubleSide
                });
            }
            
            // Apply environment map to material if available
            if (this.environmentMap) {
                glassMaterial.envMap = this.environmentMap;
                glassMaterial.envMapIntensity = 1.0;
            }
            
            const glassSprocket = new THREE.Mesh(sprocketGeometry, glassMaterial);
            glassSprocket.rotation.set(0, 0, 0);
            glassSprocket.castShadow = true;
            glassSprocket.receiveShadow = true;
            
            // Store sprocket reference for animation with machine status
            glassSprocket.userData = { 
                machineStatus: machine.status,
                machineId: machine.id
            };
            
            // Initialize sprockets array if not exists
            if (!this.machineSprockets) {
                this.machineSprockets = [];
            }
            this.machineSprockets.push(glassSprocket);
            
            circleGroup.add(glassSprocket);
            
            // Position the circle
            circleGroup.position.set(startX + (index * spacing), 0, 0);
            
            // Add CSS2D label
            const labelDiv = document.createElement('div');
            labelDiv.style.color = machine.status === 'fault' ? '#ff4444' : '#00ffff';
            labelDiv.style.fontSize = '10px';
            labelDiv.style.fontFamily = 'Courier New, monospace';
            labelDiv.style.textAlign = 'center';
            labelDiv.style.fontWeight = 'bold';
            labelDiv.innerHTML = `${machine.id}<br><span style="font-size: 8px;">${machine.name}</span>`;
            
            const label = new CSS2DObject(labelDiv);
            label.position.set(0, -60, 0);
            circleGroup.add(label);
            
            // Add status light in center
            const statusDot = document.createElement('div');
            statusDot.style.width = '8px';
            statusDot.style.height = '8px';
            
            let dotColor, glowColor;
            if (machine.status === 'fault') {
                dotColor = '#ff4444';
                glowColor = '#ff4444';
                statusDot.style.animation = 'pulseRed 1s infinite';
            } else if (machine.status === 'starved') {
                dotColor = '#000000';
                glowColor = '#333333';
            } else {
                dotColor = '#00ff00';
                glowColor = '#00ff00';
            }
            
            statusDot.style.background = dotColor;
            statusDot.style.borderRadius = '50%';
            statusDot.style.boxShadow = `0 0 10px ${glowColor}`;
            
            const statusLight = new CSS2DObject(statusDot);
            statusLight.position.set(0, 0, 1);
            circleGroup.add(statusLight);
            
            // Add diagnostics panel for faulted machines
            if (machine.status === 'fault') {
                this.createMachineDiagnostics(circleGroup, machine);
                this.createTargetingReticle(circleGroup);
            }
            
            bottomGroup.add(circleGroup);
        });
    }
    
    createMachineDiagnostics(circleGroup, machine) {
        // Create holographic diagnostics panel with targeting marker
        const diagDiv = document.createElement('div');
        diagDiv.style.background = 'rgba(0, 0, 0, 0.1)';
        diagDiv.style.border = '0.5px solid #ff4444';
        diagDiv.style.color = '#ff4444';
        diagDiv.style.fontFamily = 'Courier New, monospace';
        diagDiv.style.fontSize = '13px';  // 11 * 1.2 = 13.2 ≈ 13
        diagDiv.style.padding = '12px';   // 10 * 1.2 = 12
        diagDiv.style.width = '259px';    // 216 * 1.2 = 259.2 ≈ 259
        diagDiv.style.backdropFilter = 'blur(5px)';
        diagDiv.style.position = 'relative';
        diagDiv.style.clipPath = 'polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 8px 100%, 0 calc(100% - 8px))';
        diagDiv.style.zIndex = '9999';
        
        // Add internal grid lines for holographic effect
        diagDiv.style.backgroundImage = `
            linear-gradient(90deg, rgba(255,68,68,0.1) 1px, transparent 1px),
            linear-gradient(0deg, rgba(255,68,68,0.1) 1px, transparent 1px)
        `;
        diagDiv.style.backgroundSize = '20px 15px';
        
        // Create content lines for typewriter effect
        const lines = [
            { text: '⚠️ FAULT DETECTED', style: 'border-bottom: 0.5px solid #ff4444; margin-bottom: 6px; padding-bottom: 2px; font-weight: bold; font-size: 8px;' },
            { text: `UNIT: ${machine.name}`, style: 'margin: 2px 0; opacity: 0.9;' },
            { text: 'ERR: MOTOR OVERHEAT', style: 'margin: 2px 0; opacity: 0.9;' },
            { text: 'TEMP: 95°C (MAX: 85°C)', style: 'margin: 2px 0; opacity: 0.9;' },
            { text: 'T-DOWN: 00:14:32', style: 'margin: 2px 0; opacity: 0.9;' },
            { text: 'STATUS: COOLING CYCLE', style: 'margin: 2px 0; opacity: 0.9;' }
        ];
        
        // Store lines data for re-animation during cycling
        diagDiv.linesData = lines;
        diagDiv.lineElements = [];
        
        lines.forEach((line, index) => {
            const lineDiv = document.createElement('div');
            lineDiv.style.cssText = line.style;
            lineDiv.style.overflow = 'hidden';
            lineDiv.style.whiteSpace = 'nowrap';
            lineDiv.style.width = '0';
            diagDiv.appendChild(lineDiv);
            diagDiv.lineElements.push(lineDiv);
            
            // Animate each line with delay
            setTimeout(() => {
                this.typewriterEffect(lineDiv, line.text, 30);
            }, index * 300);
        });
        
        // Create connecting line with arrow
        const connectLine = document.createElement('div');
        connectLine.style.position = 'absolute';
        connectLine.style.bottom = '-130px';
        connectLine.style.left = '50%';
        connectLine.style.width = '0.5px';
        connectLine.style.height = '100px';
        connectLine.style.background = 'linear-gradient(to top, #ff4444 0%, rgba(255,68,68,0.3) 100%)';
        connectLine.style.transform = 'translateX(-50%)';
        connectLine.style.opacity = '0.8';
        diagDiv.appendChild(connectLine);
        
        // Create targeting arrow at panel
        const targetArrow = document.createElement('div');
        targetArrow.style.position = 'absolute';
        targetArrow.style.bottom = '-5px';
        targetArrow.style.left = '50%';
        targetArrow.style.width = '8px';
        targetArrow.style.height = '8px';
        targetArrow.style.transform = 'translateX(-50%) rotate(45deg)';
        targetArrow.style.border = '0.5px solid #ff4444';
        targetArrow.style.borderTop = 'none';
        targetArrow.style.borderLeft = 'none';
        targetArrow.style.opacity = '0.9';
        diagDiv.appendChild(targetArrow);
        
        const diagObject = new CSS2DObject(diagDiv);
        diagObject.position.set(0, 130, 10);
        circleGroup.add(diagObject);
        
        // Implement cycling visibility: 5 seconds on, 2 seconds off
        this.startDiagnosticsCycling(diagDiv, machine);
        
    }
    
    typewriterEffect(element, text, speed = 50) {
        element.innerHTML = '';
        element.style.width = 'auto';
        let i = 0;
        
        function typeChar() {
            if (i < text.length) {
                element.innerHTML += text.charAt(i);
                i++;
                setTimeout(typeChar, speed);
            }
        }
        typeChar();
    }
    
    startDiagnosticsCycling(diagDiv, machine) {
        // Only cycle if machine status is 'fault'
        if (machine.status !== 'fault') return;
        
        let isVisible = true;
        diagDiv.style.display = 'block';
        diagDiv.style.opacity = '1';
        
        // Create cycling interval: 5 seconds visible, 2 seconds hidden
        const cycleInterval = setInterval(() => {
            if (isVisible) {
                // Start fade out
                diagDiv.style.transition = 'opacity 0.3s ease-out';
                diagDiv.style.opacity = '0';
                
                // Hide completely after fade
                setTimeout(() => {
                    diagDiv.style.display = 'none';
                }, 300);
                
                isVisible = false;
                
                // Show again after 2 seconds (total off time)
                setTimeout(() => {
                    diagDiv.style.display = 'block';
                    diagDiv.style.transition = 'opacity 0.3s ease-in';
                    diagDiv.style.opacity = '1';
                    isVisible = true;
                    
                    // Trigger typewriter effect again
                    this.retriggerTypewriterEffect(diagDiv);
                }, 2000);
            }
        }, 10000); // Cycle every 10 seconds (10 seconds on, then trigger 2 seconds off)
        
        // Store interval reference for cleanup if needed
        diagDiv.cycleInterval = cycleInterval;
        
        console.log(`Started diagnostics cycling for machine ${machine.id}: 10s on, 2s off`);
    }
    
    retriggerTypewriterEffect(diagDiv) {
        // Reset all line elements for re-animation
        if (diagDiv.lineElements && diagDiv.linesData) {
            diagDiv.lineElements.forEach((lineDiv, index) => {
                // Clear current content and reset width
                lineDiv.innerHTML = '';
                lineDiv.style.width = '0';
                
                // Re-trigger typewriter effect with delay
                setTimeout(() => {
                    this.typewriterEffect(lineDiv, diagDiv.linesData[index].text, 30);
                }, index * 300);
            });
        }
    }
    
    createTargetingReticle(circleGroup) {
        // Create targeting reticle overlay on the machine orb
        const reticleDiv = document.createElement('div');
        reticleDiv.style.width = '60px';
        reticleDiv.style.height = '60px';
        reticleDiv.style.pointerEvents = 'none';
        reticleDiv.style.position = 'relative';
        
        reticleDiv.innerHTML = `
            <!-- Outer targeting ring -->
            <div style="position: absolute; top: 50%; left: 50%; width: 50px; height: 50px; border: 0.5px solid #ff4444; border-radius: 50%; transform: translate(-50%, -50%); opacity: 0.6; animation: pulseRed 2s infinite;"></div>
            <!-- Corner brackets around orb -->
            <div style="position: absolute; top: 5px; left: 5px; width: 12px; height: 12px; border-left: 0.5px solid #ff4444; border-top: 0.5px solid #ff4444; opacity: 0.8;"></div>
            <div style="position: absolute; top: 5px; right: 5px; width: 12px; height: 12px; border-right: 0.5px solid #ff4444; border-top: 0.5px solid #ff4444; opacity: 0.8;"></div>
            <div style="position: absolute; bottom: 5px; left: 5px; width: 12px; height: 12px; border-left: 0.5px solid #ff4444; border-bottom: 0.5px solid #ff4444; opacity: 0.8;"></div>
            <div style="position: absolute; bottom: 5px; right: 5px; width: 12px; height: 12px; border-right: 0.5px solid #ff4444; border-bottom: 0.5px solid #ff4444; opacity: 0.8;"></div>
            <!-- Main targeting beam extending upward -->
            <div style="position: absolute; top: -50px; left: 50%; width: 2px; height: 50px; background: linear-gradient(to top, #ff4444 0%, rgba(255,68,68,0.9) 50%, rgba(255,68,68,0.6) 100%); transform: translateX(-50%); opacity: 1; animation: pulseRed 1s infinite; box-shadow: 0 0 4px #ff4444;"></div>
            <!-- Targeting arrow at top of beam -->
            <div style="position: absolute; top: -60px; left: 50%; width: 0; height: 0; border-left: 6px solid transparent; border-right: 6px solid transparent; border-bottom: 12px solid #ff4444; transform: translateX(-50%); opacity: 1; animation: pulseRed 1.5s infinite; filter: drop-shadow(0 0 3px #ff4444);"></div>
            <!-- Side targeting brackets -->
            <div style="position: absolute; top: -30px; left: 15px; width: 8px; height: 0.5px; background: #ff4444; opacity: 0.8; animation: pulseRed 2s infinite;"></div>
            <div style="position: absolute; top: -30px; right: 15px; width: 8px; height: 0.5px; background: #ff4444; opacity: 0.8; animation: pulseRed 2s infinite;"></div>
        `;
        
        const reticleObject = new CSS2DObject(reticleDiv);
        reticleObject.position.set(0, 0, 2);
        circleGroup.add(reticleObject);
    }
    
    createRightSideCards(chartGroup) {
        const cardWidth = 300;
        const cardHeight = 160;
        const cardSpacing = 140;
        const rightX = 380; // Right side of middle section
        
        // Tactical Targeting Card (left of Active Fault) - moved up 20px
        this.createTacticalTargetingCard(chartGroup, 160, cardHeight, rightX - 230, 80);
        
        // Active Fault Overlay Card (top) - moved up 20px
        this.createActiveFaultCard(chartGroup, cardWidth, cardHeight, rightX, 80);
        
        // Last Downtime Event Card (bottom) - moved up 40px
        this.createLastDowntimeCard(chartGroup, cardWidth, cardHeight, rightX, -70);
    }
    
    createActiveFaultCard(chartGroup, width, height, x, y) {
        const faultDiv = document.createElement('div');
        faultDiv.style.width = width + 'px';
        faultDiv.style.height = height + 'px';
        faultDiv.style.background = 'rgba(0, 8, 15, 0.9)';
        faultDiv.style.border = '2px solid #00d4ff';
        faultDiv.style.borderRadius = '4px';
        faultDiv.style.padding = '15px';
        faultDiv.style.color = '#00d4ff';
        faultDiv.style.fontFamily = '"Courier New", "Consolas", "Monaco", monospace';
        faultDiv.style.boxSizing = 'border-box';
        faultDiv.style.display = 'flex';
        faultDiv.style.flexDirection = 'column';
        faultDiv.style.backdropFilter = 'blur(50px)';
        faultDiv.style.boxShadow = '0 0 25px #00d4ff60, inset 0 0 10px rgba(0, 212, 255, 0.1)';
        faultDiv.style.position = 'relative';
        faultDiv.style.zIndex = '2';
        faultDiv.id = 'active-fault-card';
        faultDiv.className = 'scan-target';
        
        // Add fighter jet style scan lines
        const scanLines = document.createElement('div');
        scanLines.style.position = 'absolute';
        scanLines.style.top = '0';
        scanLines.style.left = '0';
        scanLines.style.width = '100%';
        scanLines.style.height = '100%';
        scanLines.style.background = `repeating-linear-gradient(
            0deg,
            transparent,
            transparent 2px,
            rgba(0, 212, 255, 0.03) 2px,
            rgba(0, 212, 255, 0.03) 4px
        )`;
        scanLines.style.pointerEvents = 'none';
        faultDiv.appendChild(scanLines);
        
        // Add status light strip at top
        const statusLightStrip = document.createElement('div');
        statusLightStrip.style.position = 'absolute';
        statusLightStrip.style.top = '5px';
        statusLightStrip.style.right = '20px';
        statusLightStrip.style.display = 'flex';
        statusLightStrip.style.gap = '5px';
        
        // Create 3 status lights
        for (let i = 0; i < 3; i++) {
            const light = document.createElement('div');
            light.style.width = '8px';
            light.style.height = '8px';
            light.style.borderRadius = '50%';
            light.style.border = '1px solid #00d4ff';
            light.style.backgroundColor = i === 0 ? '#ff4444' : (i === 1 ? '#ffff00' : '#00d4ff');
            light.style.boxShadow = i === 0 ? '0 0 10px #ff4444' : (i === 1 ? '0 0 10px #ffff00' : '0 0 10px #00d4ff');
            if (i === 0) {
                light.style.animation = 'pulseRed 1s infinite';
            }
            statusLightStrip.appendChild(light);
        }
        faultDiv.appendChild(statusLightStrip);
        
        // Header
        const header = document.createElement('div');
        header.style.fontSize = '12px';
        header.style.fontWeight = 'bold';
        header.style.textTransform = 'uppercase';
        header.style.letterSpacing = '2px';
        header.style.marginBottom = '12px';
        header.style.marginTop = '0px'; // No longer need margin - in separate section
        header.style.textShadow = '0 0 8px #00d4ff';
        header.style.borderBottom = '1px solid #00d4ff40';
        header.style.paddingBottom = '6px';
        header.style.position = 'relative';
        header.style.zIndex = '2';
        header.style.color = '#00d4ff';
        header.textContent = '◢ ACTIVE FAULT OVERLAY ◤';
        
        // Machine name that caused the fault
        const machineName = document.createElement('div');
        machineName.style.color = '#ffffff';
        machineName.style.fontSize = '14px';
        machineName.style.fontWeight = '700';
        machineName.style.marginBottom = '8px';
        machineName.style.textShadow = '0 0 8px #00d4ff';
        machineName.textContent = 'Machine: PRESS-001';
        
        // Growing line container representing downtime duration
        const downtimeLineContainer = document.createElement('div');
        downtimeLineContainer.style.width = '100%';
        downtimeLineContainer.style.height = '6px';
        downtimeLineContainer.style.backgroundColor = 'rgba(0, 212, 255, 0.1)';
        downtimeLineContainer.style.borderRadius = '3px';
        downtimeLineContainer.style.marginBottom = '12px';
        downtimeLineContainer.style.position = 'relative';
        downtimeLineContainer.style.overflow = 'hidden';
        
        // Growing line bar
        const growingLine = document.createElement('div');
        growingLine.style.height = '100%';
        growingLine.style.backgroundColor = '#00d4ff';
        growingLine.style.borderRadius = '3px';
        growingLine.style.boxShadow = '0 0 10px #00d4ff';
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
            <div style="color: #00d4ff; font-size: 10px; font-weight: 600; margin-bottom: 4px;">MTTR</div>
            <div style="color: #ffffff; font-size: 16px; font-weight: 700;">8.2</div>
            <div style="color: rgba(255,255,255,0.6); font-size: 9px;">minutes</div>
        `;
        
        // MTBF column
        const mtbfColumn = document.createElement('div');
        mtbfColumn.style.textAlign = 'center';
        mtbfColumn.innerHTML = `
            <div style="color: #00d4ff; font-size: 10px; font-weight: 600; margin-bottom: 4px;">MTBF</div>
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
    
    createTacticalTargetingRing(container) {
        // Create SVG for precise tactical elements
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.style.position = 'absolute';
        svg.style.top = '0';
        svg.style.left = '0';
        svg.style.width = '100%';
        svg.style.height = '100%';
        svg.style.pointerEvents = 'none';
        
        const centerX = 50; // Moved entire reticle 5px to the left
        const centerY = 55;
        const outerRadius = 45;
        const innerRadius = 36;
        
        // Outer targeting ring with crosshairs
        const outerRing = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        outerRing.setAttribute('cx', centerX);
        outerRing.setAttribute('cy', centerY);
        outerRing.setAttribute('r', outerRadius);
        outerRing.setAttribute('fill', 'none');
        outerRing.setAttribute('stroke', '#00d4ff');
        outerRing.setAttribute('stroke-width', '2');
        outerRing.setAttribute('opacity', '1');
        svg.appendChild(outerRing);
        
        // Crosshairs (N, S, E, W)
        const crosshairs = [
            { x1: centerX, y1: centerY - outerRadius - 3, x2: centerX, y2: centerY - outerRadius + 3 }, // N
            { x1: centerX, y1: centerY + outerRadius - 3, x2: centerX, y2: centerY + outerRadius + 3 }, // S
            { x1: centerX + outerRadius - 3, y1: centerY, x2: centerX + outerRadius + 3, y2: centerY }, // E
            { x1: centerX - outerRadius - 3, y1: centerY, x2: centerX - outerRadius + 3, y2: centerY }  // W
        ];
        
        crosshairs.forEach(ch => {
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', ch.x1);
            line.setAttribute('y1', ch.y1);
            line.setAttribute('x2', ch.x2);
            line.setAttribute('y2', ch.y2);
            line.setAttribute('stroke', '#00d4ff');
            line.setAttribute('stroke-width', '2');
            line.setAttribute('opacity', '1');
            svg.appendChild(line);
        });
        
        // Corner acquisition brackets
        const brackets = [
            // Top-left
            [[centerX - 20, centerY - 20], [centerX - 14, centerY - 20], [centerX - 20, centerY - 14]],
            // Top-right  
            [[centerX + 20, centerY - 20], [centerX + 14, centerY - 20], [centerX + 20, centerY - 14]],
            // Bottom-left
            [[centerX - 20, centerY + 20], [centerX - 14, centerY + 20], [centerX - 20, centerY + 14]],
            // Bottom-right
            [[centerX + 20, centerY + 20], [centerX + 14, centerY + 20], [centerX + 20, centerY + 14]]
        ];
        
        brackets.forEach(bracket => {
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            const pathData = `M${bracket[0][0]},${bracket[0][1]} L${bracket[1][0]},${bracket[1][1]} L${bracket[2][0]},${bracket[2][1]}`;
            path.setAttribute('d', pathData);
            path.setAttribute('fill', 'none');
            path.setAttribute('stroke', '#00d4ff');
            path.setAttribute('stroke-width', '2');
            path.setAttribute('opacity', '1');
            svg.appendChild(path);
        });
        
        // Progress arc (starts empty, fills clockwise)
        const progressArc = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        progressArc.setAttribute('fill', 'none');
        progressArc.setAttribute('stroke', '#00d4ff');
        progressArc.setAttribute('stroke-width', '3');
        progressArc.setAttribute('stroke-linecap', 'round');
        progressArc.setAttribute('opacity', '1');
        progressArc.id = 'progress-arc-' + container.id;
        svg.appendChild(progressArc);
        
        // Rotating radar sweep line
        const radarSweep = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        radarSweep.setAttribute('x1', centerX);
        radarSweep.setAttribute('y1', centerY);
        radarSweep.setAttribute('x2', centerX);
        radarSweep.setAttribute('y2', centerY - innerRadius);
        radarSweep.setAttribute('stroke', '#00d4ff');
        radarSweep.setAttribute('stroke-width', '2');
        radarSweep.setAttribute('opacity', '0.8');
        radarSweep.style.transformOrigin = `${centerX}px ${centerY}px`;
        radarSweep.style.animation = 'spin 4s linear infinite';
        svg.appendChild(radarSweep);
        
        container.appendChild(svg);
        
        // Add tactical text elements
        this.createTacticalTextElements(container);
        
        // Start progress animation
        this.animateTargetingProgress(progressArc, centerX, centerY, innerRadius);
    }
    
    createTacticalTextElements(container) {
        // Target designation - positioned within card boundaries
        const targetLabel = document.createElement('div');
        targetLabel.style.position = 'absolute';
        targetLabel.style.top = '-14px';
        targetLabel.style.right = '-10px';
        targetLabel.style.fontSize = '10px';
        targetLabel.style.color = '#00d4ff';
        targetLabel.style.fontFamily = 'monospace';
        targetLabel.style.fontWeight = 'bold';
        targetLabel.style.textShadow = '0 0 5px #00d4ff';
        targetLabel.style.whiteSpace = 'nowrap';
        targetLabel.textContent = 'TGT:F-001';
        container.appendChild(targetLabel);
        
        // Status indicator - positioned within card boundaries
        const statusLabel = document.createElement('div');
        statusLabel.style.position = 'absolute';
        statusLabel.style.bottom = '-14px';
        statusLabel.style.right = '-5px';
        statusLabel.style.fontSize = '10px';
        statusLabel.style.color = '#ff4444';
        statusLabel.style.fontFamily = 'monospace';
        statusLabel.style.fontWeight = 'bold';
        statusLabel.style.textShadow = '0 0 5px #ff4444';
        statusLabel.style.whiteSpace = 'nowrap';
        statusLabel.textContent = 'ACTIVE';
        statusLabel.style.animation = 'pulse 1s infinite';
        container.appendChild(statusLabel);
        
        // Range/Time display - positioned within card boundaries
        const rangeLabel = document.createElement('div');
        rangeLabel.style.position = 'absolute';
        rangeLabel.style.bottom = '-14px';
        rangeLabel.style.left = '-10px';
        rangeLabel.style.fontSize = '10px';
        rangeLabel.style.color = '#00d4ff';
        rangeLabel.style.fontFamily = 'monospace';
        rangeLabel.style.fontWeight = 'bold';
        rangeLabel.style.textShadow = '0 0 5px #00d4ff';
        rangeLabel.style.whiteSpace = 'nowrap';
        rangeLabel.textContent = 'RNG:00:00';
        rangeLabel.id = 'range-timer-' + container.id;
        container.appendChild(rangeLabel);
        
        // Start timer updates
        this.startTargetingTimer(rangeLabel);
    }
    
    animateTargetingProgress(arc, centerX, centerY, radius) {
        let progress = 0;
        const duration = 600000; // 10 minutes in milliseconds
        const startTime = Date.now();
        
        const updateProgress = () => {
            const elapsed = Date.now() - startTime;
            progress = Math.min(elapsed / duration, 1);
            
            // Calculate arc path
            const angle = progress * 2 * Math.PI - Math.PI/2; // Start at top
            const largeArcFlag = progress > 0.5 ? 1 : 0;
            const endX = centerX + radius * Math.cos(angle);
            const endY = centerY + radius * Math.sin(angle);
            
            if (progress > 0) {
                const pathData = `M ${centerX} ${centerY - radius} A ${radius} ${radius} 0 ${largeArcFlag} 1 ${endX} ${endY}`;
                arc.setAttribute('d', pathData);
                
                // Change color based on progress
                if (progress < 0.3) {
                    arc.setAttribute('stroke', '#00d4ff');
                } else if (progress < 0.7) {
                    arc.setAttribute('stroke', '#ffaa00');
                } else {
                    arc.setAttribute('stroke', '#ff4444');
                    arc.style.animation = 'pulse 0.5s infinite';
                }
            }
            
            if (progress < 1) {
                requestAnimationFrame(updateProgress);
            } else {
                // Full circle - start continuous rotation
                arc.style.animation = 'spin 2s linear infinite';
            }
        };
        
        updateProgress();
    }
    
    startTargetingTimer(label) {
        const startTime = Date.now();
        
        const updateTimer = () => {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const minutes = Math.floor(elapsed / 60).toString().padStart(2, '0');
            const seconds = (elapsed % 60).toString().padStart(2, '0');
            label.textContent = `RNG:${minutes}:${seconds}`;
            
            setTimeout(updateTimer, 1000);
        };
        
        updateTimer();
    }
    
    createTacticalTargetingCard(chartGroup, width, height, x, y) {
        const targetingDiv = document.createElement('div');
        targetingDiv.style.width = width + 'px';
        targetingDiv.style.height = height + 'px';
        targetingDiv.style.background = 'rgba(0, 8, 15, 0.9)';
        targetingDiv.style.border = '2px solid #00d4ff';
        targetingDiv.style.borderRadius = '4px';
        targetingDiv.style.padding = '15px';
        targetingDiv.style.color = '#00d4ff';
        targetingDiv.style.fontFamily = '"Courier New", "Consolas", "Monaco", monospace';
        targetingDiv.style.boxSizing = 'border-box';
        targetingDiv.style.display = 'flex';
        targetingDiv.style.alignItems = 'center';
        targetingDiv.style.justifyContent = 'center';
        targetingDiv.style.backdropFilter = 'blur(50px)';
        targetingDiv.style.boxShadow = '0 0 25px #00d4ff60, inset 0 0 10px rgba(0, 212, 255, 0.1)';
        targetingDiv.style.position = 'relative';
        targetingDiv.style.zIndex = '2';
        targetingDiv.id = 'tactical-targeting-card';
        targetingDiv.className = 'scan-target';
        
        // Add fighter jet style scan lines
        const scanLines = document.createElement('div');
        scanLines.style.position = 'absolute';
        scanLines.style.top = '0';
        scanLines.style.left = '0';
        scanLines.style.width = '100%';
        scanLines.style.height = '100%';
        scanLines.style.background = `repeating-linear-gradient(
            0deg,
            transparent,
            transparent 2px,
            rgba(0, 212, 255, 0.03) 2px,
            rgba(0, 212, 255, 0.03) 4px
        )`;
        scanLines.style.pointerEvents = 'none';
        targetingDiv.appendChild(scanLines);
        
        // Create tactical targeting system container - moved 10px to the right
        const targetingContainer = document.createElement('div');
        targetingContainer.style.position = 'relative';
        targetingContainer.style.width = '110px';
        targetingContainer.style.height = '110px';
        targetingContainer.style.marginLeft = '10px';
        targetingContainer.style.pointerEvents = 'none';
        targetingContainer.style.zIndex = '5';
        targetingContainer.id = 'targeting-system-' + Date.now();
        
        
        // Create tactical targeting ring system
        this.createTacticalTargetingRing(targetingContainer);
        
        targetingDiv.appendChild(targetingContainer);
        
        const targetingObject = new CSS2DObject(targetingDiv);
        targetingObject.position.set(x, y, 0);
        targetingObject.center.set(0.5, 0.5);
        
        chartGroup.add(targetingObject);
    }
    
    createLastDowntimeCard(chartGroup, width, height, x, y) {
        const downtimeDiv = document.createElement('div');
        downtimeDiv.style.width = width + 'px';
        downtimeDiv.style.height = height + 'px';
        downtimeDiv.style.background = 'rgba(0, 8, 15, 0.9)';
        downtimeDiv.style.border = '2px solid #00d4ff';
        downtimeDiv.style.borderRadius = '4px';
        downtimeDiv.style.padding = '15px';
        downtimeDiv.style.color = '#00d4ff';
        downtimeDiv.style.fontFamily = '"Courier New", "Consolas", "Monaco", monospace';
        downtimeDiv.style.boxSizing = 'border-box';
        downtimeDiv.style.display = 'flex';
        downtimeDiv.style.flexDirection = 'column';
        downtimeDiv.style.backdropFilter = 'blur(50px)';
        downtimeDiv.style.boxShadow = '0 0 25px #00d4ff60, inset 0 0 10px rgba(0, 212, 255, 0.1)';
        downtimeDiv.style.position = 'relative';
        downtimeDiv.style.zIndex = '2';
        downtimeDiv.className = 'scan-target';
        
        // Add fighter jet style scan lines
        const scanLines = document.createElement('div');
        scanLines.style.position = 'absolute';
        scanLines.style.top = '0';
        scanLines.style.left = '0';
        scanLines.style.width = '100%';
        scanLines.style.height = '100%';
        scanLines.style.background = `repeating-linear-gradient(
            0deg,
            transparent,
            transparent 2px,
            rgba(0, 212, 255, 0.03) 2px,
            rgba(0, 212, 255, 0.03) 4px
        )`;
        scanLines.style.pointerEvents = 'none';
        downtimeDiv.appendChild(scanLines);
        
        // Add status light strip
        const statusLightStrip = document.createElement('div');
        statusLightStrip.style.position = 'absolute';
        statusLightStrip.style.top = '5px';
        statusLightStrip.style.right = '20px';
        statusLightStrip.style.display = 'flex';
        statusLightStrip.style.gap = '5px';
        
        for (let i = 0; i < 3; i++) {
            const light = document.createElement('div');
            light.style.width = '8px';
            light.style.height = '8px';
            light.style.borderRadius = '50%';
            light.style.border = '1px solid #00d4ff';
            light.style.backgroundColor = '#00d4ff';
            light.style.boxShadow = '0 0 10px #00d4ff';
            statusLightStrip.appendChild(light);
        }
        downtimeDiv.appendChild(statusLightStrip);
        
        // Header
        const header = document.createElement('div');
        header.style.fontSize = '12px';
        header.style.fontWeight = 'bold';
        header.style.textTransform = 'uppercase';
        header.style.letterSpacing = '2px';
        header.style.marginBottom = '12px';
        header.style.textShadow = '0 0 8px #00d4ff';
        header.style.borderBottom = '1px solid #00d4ff40';
        header.style.paddingBottom = '6px';
        header.style.position = 'relative';
        header.style.zIndex = '2';
        header.style.color = '#00d4ff';
        header.textContent = '◢ LAST DOWNTIME EVENT ◤';
        
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
    
    createSprocketOverlayCards(bottomGroup) {
        console.log('CREATING SPROCKET OVERLAY CARDS - Above Machine Status');
        
        const cardWidth = 250;
        const cardHeight = 140;
        const cardSpacing = 280;
        // Align with left margin of chart: chartX (-150) - chartWidth/2 (338) = -488
        // Move 100 pixels to the right: -488 + 100 = -388
        const chartLeftMargin = -488;
        const startX = chartLeftMargin + 100;
        const cardY = 120; // Position above sprockets
        
        const cardData = [
            {
                title: 'PRODUCTION RATE',
                status: 'TRACKING',
                plannedRate: '950',
                currentRate: '847',
                color: '#00d4ff',
                statusColor: '#00d4ff'
            },
            {
                title: 'SHIFT TOTALS',
                status: 'ACTIVE',
                plannedShiftTotal: '7600',
                currentShiftTotal: '5890',
                color: '#00d4ff',
                statusColor: '#00d4ff'
            }
        ];
        
        cardData.forEach((card, index) => {
            const cardGroup = new THREE.Group();
            
            // Create futuristic border frame
            this.createSprocketCardFrame(cardGroup, cardWidth, cardHeight, card.color);
            
            // Create HTML content
            const cardDiv = document.createElement('div');
            cardDiv.style.width = cardWidth + 'px';
            cardDiv.style.height = cardHeight + 'px';
            cardDiv.style.background = 'rgba(0, 8, 15, 0.9)';
            cardDiv.style.border = `2px solid ${card.color}`;
            cardDiv.style.borderRadius = '4px';
            cardDiv.style.padding = '15px';
            cardDiv.style.color = card.color;
            cardDiv.style.fontFamily = '"Courier New", "Consolas", "Monaco", monospace';
            cardDiv.style.display = 'flex';
            cardDiv.style.flexDirection = 'column';
            cardDiv.style.backdropFilter = 'blur(50px)';
            cardDiv.style.boxShadow = `0 0 25px ${card.color}60, inset 0 0 10px rgba(0, 212, 255, 0.1)`;
            cardDiv.style.position = 'relative';
            cardDiv.style.zIndex = '1'; // Lower z-index for background cards
            
            // Add fighter jet style scan lines
            const scanLines = document.createElement('div');
            scanLines.style.position = 'absolute';
            scanLines.style.top = '0';
            scanLines.style.left = '0';
            scanLines.style.width = '100%';
            scanLines.style.height = '100%';
            scanLines.style.background = `repeating-linear-gradient(
                0deg,
                transparent,
                transparent 2px,
                rgba(0, 212, 255, 0.03) 2px,
                rgba(0, 212, 255, 0.03) 4px
            )`;
            scanLines.style.pointerEvents = 'none';
            cardDiv.appendChild(scanLines);
            
            // Header
            const header = document.createElement('div');
            header.style.fontSize = '12px';
            header.style.fontWeight = 'bold';
            header.style.textTransform = 'uppercase';
            header.style.letterSpacing = '2px';
            header.style.marginBottom = '12px';
            header.style.textShadow = `0 0 8px ${card.color}`;
            header.style.borderBottom = `1px solid ${card.color}40`;
            header.style.paddingBottom = '6px';
            header.style.position = 'relative';
            header.style.zIndex = '2';
            header.textContent = `◢ ${card.title} ◤`;
            
            // Status indicator
            const statusDiv = document.createElement('div');
            statusDiv.style.display = 'flex';
            statusDiv.style.alignItems = 'center';
            statusDiv.style.marginBottom = '12px';
            statusDiv.style.position = 'relative';
            statusDiv.style.zIndex = '2';
            
            // Military style status indicator
            const statusIndicator = document.createElement('div');
            statusIndicator.style.display = 'flex';
            statusIndicator.style.alignItems = 'center';
            statusIndicator.style.padding = '4px 8px';
            statusIndicator.style.background = `linear-gradient(45deg, rgba(0, 212, 255, 0.1), rgba(0, 212, 255, 0.05))`;
            statusIndicator.style.border = `1px solid ${card.statusColor}`;
            statusIndicator.style.borderRadius = '2px';
            
            const statusLight = document.createElement('div');
            statusLight.style.width = '6px';
            statusLight.style.height = '6px';
            statusLight.style.background = card.statusColor;
            statusLight.style.marginRight = '6px';
            statusLight.style.boxShadow = `0 0 8px ${card.statusColor}`;
            statusLight.style.animation = 'pulse 1.5s infinite';
            
            const statusText = document.createElement('span');
            statusText.style.fontSize = '10px';
            statusText.style.fontWeight = 'bold';
            statusText.style.color = card.statusColor;
            statusText.style.letterSpacing = '1px';
            statusText.textContent = `● ${card.status}`;
            
            statusIndicator.appendChild(statusLight);
            statusIndicator.appendChild(statusText);
            statusDiv.appendChild(statusIndicator);
            
            // Metrics
            const metricsDiv = document.createElement('div');
            metricsDiv.style.display = 'flex';
            metricsDiv.style.justifyContent = 'space-between';
            metricsDiv.style.flexGrow = '1';
            metricsDiv.style.alignItems = 'center';
            metricsDiv.style.position = 'relative';
            metricsDiv.style.zIndex = '2';
            
            if (index === 0) {
                // Left card: Production Rate
                const plannedRateDiv = document.createElement('div');
                plannedRateDiv.style.textAlign = 'center';
                plannedRateDiv.style.padding = '8px';
                plannedRateDiv.style.border = `1px solid ${card.color}30`;
                plannedRateDiv.style.borderRadius = '2px';
                plannedRateDiv.style.background = `rgba(0, 212, 255, 0.05)`;
                plannedRateDiv.innerHTML = `
                    <div style="font-size: 9px; opacity: 0.8; margin-bottom: 4px; letter-spacing: 1px; color: ${card.color};">▸ PLANNED RATE</div>
                    <div style="font-size: 14px; font-weight: bold; text-shadow: 0 0 6px ${card.color}; color: ${card.color};">${card.plannedRate}</div>
                `;
                
                const currentRateDiv = document.createElement('div');
                currentRateDiv.style.textAlign = 'center';
                currentRateDiv.style.padding = '8px';
                currentRateDiv.style.border = `1px solid ${card.color}30`;
                currentRateDiv.style.borderRadius = '2px';
                currentRateDiv.style.background = `rgba(0, 212, 255, 0.05)`;
                currentRateDiv.innerHTML = `
                    <div style="font-size: 9px; opacity: 0.8; margin-bottom: 4px; letter-spacing: 1px; color: ${card.color};">▸ CURRENT RATE</div>
                    <div style="font-size: 14px; font-weight: bold; text-shadow: 0 0 6px ${card.color}; color: ${card.color};">${card.currentRate}</div>
                `;
                
                metricsDiv.appendChild(plannedRateDiv);
                metricsDiv.appendChild(currentRateDiv);
            } else {
                // Right card: Shift Totals
                const plannedShiftDiv = document.createElement('div');
                plannedShiftDiv.style.textAlign = 'center';
                plannedShiftDiv.style.padding = '8px';
                plannedShiftDiv.style.border = `1px solid ${card.color}30`;
                plannedShiftDiv.style.borderRadius = '2px';
                plannedShiftDiv.style.background = `rgba(0, 212, 255, 0.05)`;
                plannedShiftDiv.innerHTML = `
                    <div style="font-size: 9px; opacity: 0.8; margin-bottom: 4px; letter-spacing: 1px; color: ${card.color};">▸ PLANNED SHIFT TOTAL</div>
                    <div style="font-size: 14px; font-weight: bold; text-shadow: 0 0 6px ${card.color}; color: ${card.color};">${card.plannedShiftTotal}</div>
                `;
                
                const currentShiftDiv = document.createElement('div');
                currentShiftDiv.style.textAlign = 'center';
                currentShiftDiv.style.padding = '8px';
                currentShiftDiv.style.border = `1px solid ${card.color}30`;
                currentShiftDiv.style.borderRadius = '2px';
                currentShiftDiv.style.background = `rgba(0, 212, 255, 0.05)`;
                currentShiftDiv.innerHTML = `
                    <div style="font-size: 9px; opacity: 0.8; margin-bottom: 4px; letter-spacing: 1px; color: ${card.color};">▸ CURRENT SHIFT TOTAL</div>
                    <div style="font-size: 14px; font-weight: bold; text-shadow: 0 0 6px ${card.color}; color: ${card.color};">${card.currentShiftTotal}</div>
                `;
                
                metricsDiv.appendChild(plannedShiftDiv);
                metricsDiv.appendChild(currentShiftDiv);
            }
            
            cardDiv.appendChild(header);
            cardDiv.appendChild(statusDiv);
            cardDiv.appendChild(metricsDiv);
            
            const cardObject = new CSS2DObject(cardDiv);
            cardObject.position.set(0, 0, 0);
            cardObject.center.set(0.5, 0.5);
            cardGroup.add(cardObject);
            
            // Position the card (send to back with negative z)
            cardGroup.position.set(startX + (index * cardSpacing), cardY, -50);
            bottomGroup.add(cardGroup);
        });
    }
    
    createSprocketCardFrame(cardGroup, width, height, color) {
        // Create fighter jet style angled brackets
        const bracketLength = 20;
        const bracketWidth = 1.5;
        const cornerOffset = 8;
        
        const frameMaterial = new THREE.MeshBasicMaterial({
            color: 0x00d4ff,
            transparent: true,
            opacity: 0.9
        });
        
        // Create angled corner brackets like fighter jet HUD
        const corners = [
            { pos: [-width/2 + cornerOffset, height/2 - cornerOffset], angles: [0.3, -0.3] },     // TL
            { pos: [width/2 - cornerOffset, height/2 - cornerOffset], angles: [-0.3, 0.3] },     // TR
            { pos: [-width/2 + cornerOffset, -height/2 + cornerOffset], angles: [-0.3, 0.3] },   // BL
            { pos: [width/2 - cornerOffset, -height/2 + cornerOffset], angles: [0.3, -0.3] }     // BR
        ];
        
        corners.forEach((corner, index) => {
            // Angled horizontal bracket
            const hBracket = new THREE.PlaneGeometry(bracketLength, bracketWidth);
            const hMesh = new THREE.Mesh(hBracket, frameMaterial.clone());
            hMesh.position.set(corner.pos[0], corner.pos[1], -2);
            hMesh.rotation.z = corner.angles[0];
            
            // Angled vertical bracket
            const vBracket = new THREE.PlaneGeometry(bracketWidth, bracketLength);
            const vMesh = new THREE.Mesh(vBracket, frameMaterial.clone());
            vMesh.position.set(corner.pos[0], corner.pos[1], -2);
            vMesh.rotation.z = corner.angles[1];
            
            // Add targeting markers
            const marker = new THREE.PlaneGeometry(3, 0.5);
            const markerMesh = new THREE.Mesh(marker, frameMaterial.clone());
            markerMesh.position.set(corner.pos[0], corner.pos[1], -1.5);
            markerMesh.rotation.z = Math.PI/4 * index;
            
            cardGroup.add(hMesh);
            cardGroup.add(vMesh);
            cardGroup.add(markerMesh);
        });
        
        // Add central targeting crosshairs
        const crosshairH = new THREE.PlaneGeometry(width * 0.15, 0.5);
        const crosshairV = new THREE.PlaneGeometry(0.5, height * 0.15);
        const crosshairMaterial = frameMaterial.clone();
        crosshairMaterial.opacity = 0.3;
        
        const crossH = new THREE.Mesh(crosshairH, crosshairMaterial);
        const crossV = new THREE.Mesh(crosshairV, crosshairMaterial);
        crossH.position.set(0, 0, -3);
        crossV.position.set(0, 0, -3);
        
        cardGroup.add(crossH);
        cardGroup.add(crossV);
    }
    
    createGeometricFrames(chartGroup, chartX, chartY, chartWidth, chartHeight) {
        console.log('CREATING GEOMETRIC FRAMES - Military HUD Mode Active');
        // Create angled HUD frames around chart
        this.createAngledFrame(chartGroup, chartX, chartY, chartWidth, chartHeight, 'chart');
        
        // Create frames around right side cards
        this.createAngledFrame(chartGroup, 380, 60, 300, 160, 'fault-card');
        this.createAngledFrame(chartGroup, 380, -110, 300, 160, 'downtime-card');
    }
    
    createAngledFrame(parent, x, y, width, height, frameId) {
        console.log(`Creating angled frame for ${frameId} at position (${x}, ${y})`);
        const frameGroup = new THREE.Group();
        const frameWidth = 1.5; // Thicker than top section brackets
        
        // Create angled corner brackets (military style)
        const bracketLength = 25;
        const cornerOffset = 10;
        
        // Corner notch dimensions
        const notchSize = 8;
        
        // Frame material with cyan
        const frameMaterial = new THREE.MeshBasicMaterial({
            color: 0x00d4ff, // Cyan
            transparent: true,
            opacity: 0.8,
            blending: THREE.AdditiveBlending
        });
        
        // TOP-LEFT angled bracket
        const tlHorizontal = new THREE.PlaneGeometry(bracketLength, frameWidth);
        const tlHMesh = new THREE.Mesh(tlHorizontal, frameMaterial.clone());
        tlHMesh.position.set(-width/2 + bracketLength/2 + cornerOffset, height/2 - cornerOffset, 2);
        tlHMesh.rotation.z = -0.2; // Angled like fighter jet displays
        
        const tlVertical = new THREE.PlaneGeometry(frameWidth, bracketLength);
        const tlVMesh = new THREE.Mesh(tlVertical, frameMaterial.clone());
        tlVMesh.position.set(-width/2 + cornerOffset, height/2 - bracketLength/2 - cornerOffset, 2);
        tlVMesh.rotation.z = 0.2;
        
        // TOP-RIGHT angled bracket
        const trHorizontal = new THREE.PlaneGeometry(bracketLength, frameWidth);
        const trHMesh = new THREE.Mesh(trHorizontal, frameMaterial.clone());
        trHMesh.position.set(width/2 - bracketLength/2 - cornerOffset, height/2 - cornerOffset, 2);
        trHMesh.rotation.z = 0.2;
        
        const trVertical = new THREE.PlaneGeometry(frameWidth, bracketLength);
        const trVMesh = new THREE.Mesh(trVertical, frameMaterial.clone());
        trVMesh.position.set(width/2 - cornerOffset, height/2 - bracketLength/2 - cornerOffset, 2);
        trVMesh.rotation.z = -0.2;
        
        // BOTTOM-LEFT angled bracket
        const blHorizontal = new THREE.PlaneGeometry(bracketLength, frameWidth);
        const blHMesh = new THREE.Mesh(blHorizontal, frameMaterial.clone());
        blHMesh.position.set(-width/2 + bracketLength/2 + cornerOffset, -height/2 + cornerOffset, 2);
        blHMesh.rotation.z = 0.2;
        
        const blVertical = new THREE.PlaneGeometry(frameWidth, bracketLength);
        const blVMesh = new THREE.Mesh(blVertical, frameMaterial.clone());
        blVMesh.position.set(-width/2 + cornerOffset, -height/2 + bracketLength/2 + cornerOffset, 2);
        blVMesh.rotation.z = -0.2;
        
        // BOTTOM-RIGHT angled bracket
        const brHorizontal = new THREE.PlaneGeometry(bracketLength, frameWidth);
        const brHMesh = new THREE.Mesh(brHorizontal, frameMaterial.clone());
        brHMesh.position.set(width/2 - bracketLength/2 - cornerOffset, -height/2 + cornerOffset, 2);
        brHMesh.rotation.z = -0.2;
        
        const brVertical = new THREE.PlaneGeometry(frameWidth, bracketLength);
        const brVMesh = new THREE.Mesh(brVertical, frameMaterial.clone());
        brVMesh.position.set(width/2 - cornerOffset, -height/2 + bracketLength/2 + cornerOffset, 2);
        brVMesh.rotation.z = 0.2;
        
        // Add technical markings
        for (let i = 0; i < 4; i++) {
            const marking = new THREE.PlaneGeometry(3, 0.5);
            const markingMesh = new THREE.Mesh(marking, frameMaterial.clone());
            const angle = (i * Math.PI / 2);
            const markingRadius = Math.min(width, height) * 0.6;
            markingMesh.position.set(
                Math.cos(angle) * markingRadius,
                Math.sin(angle) * markingRadius,
                2
            );
            markingMesh.rotation.z = angle + Math.PI/2;
            frameGroup.add(markingMesh);
        }
        
        // Add corner notches
        const notchPositions = [
            [-width/2 + notchSize, height/2 - notchSize],
            [width/2 - notchSize, height/2 - notchSize],
            [-width/2 + notchSize, -height/2 + notchSize],
            [width/2 - notchSize, -height/2 + notchSize]
        ];
        
        notchPositions.forEach(([nx, ny]) => {
            const notch = new THREE.PlaneGeometry(notchSize, notchSize);
            const notchMesh = new THREE.Mesh(notch, frameMaterial.clone());
            notchMesh.position.set(nx, ny, 1.5);
            notchMesh.material.opacity = 0.6;
            frameGroup.add(notchMesh);
        });
        
        // Add all bracket pieces
        frameGroup.add(tlHMesh);
        frameGroup.add(tlVMesh);
        frameGroup.add(trHMesh);
        frameGroup.add(trVMesh);
        frameGroup.add(blHMesh);
        frameGroup.add(blVMesh);
        frameGroup.add(brHMesh);
        frameGroup.add(brVMesh);
        
        // Store for animation
        frameGroup.userData.frameId = frameId;
        frameGroup.userData.animPhase = Math.random() * Math.PI * 2;
        
        // Position frame group
        frameGroup.position.set(x, y, 0);
        parent.add(frameGroup);
        
        return frameGroup;
    }
    
    createTestSprocket(bottomGroup) {
        // Create a 3D gear matching the reference image with rectangular teeth
        const sprocketGroup = new THREE.Group();
        
        // Gear dimensions matching reference
        const outerRadius = 50;
        const innerRadius = 20;
        const thickness = 20;
        const teethCount = 8; // 8 teeth like in the reference image
        
        // Create gear shape with rectangular teeth
        const gearShape = new THREE.Shape();
        
        // Build gear profile with rectangular teeth
        const toothWidth = (Math.PI * 2) / teethCount * 0.4; // Tooth width
        const gapWidth = (Math.PI * 2) / teethCount * 0.6;   // Gap width
        
        for (let i = 0; i < teethCount; i++) {
            const startAngle = i * (Math.PI * 2) / teethCount;
            
            // Tooth profile (rectangular)
            const angles = [
                startAngle,
                startAngle + toothWidth * 0.5,
                startAngle + toothWidth,
                startAngle + toothWidth + gapWidth * 0.5,
                startAngle + toothWidth + gapWidth
            ];
            
            const radii = [
                innerRadius * 1.8, // Base radius
                outerRadius,       // Tooth tip
                outerRadius,       // Tooth tip
                innerRadius * 1.8, // Base radius
                innerRadius * 1.8  // Base radius
            ];
            
            angles.forEach((angle, idx) => {
                const x = Math.cos(angle) * radii[idx];
                const y = Math.sin(angle) * radii[idx];
                
                if (i === 0 && idx === 0) {
                    gearShape.moveTo(x, y);
                } else {
                    gearShape.lineTo(x, y);
                }
            });
        }
        
        // Close the shape
        gearShape.closePath();
        
        // Add center hole
        const holePath = new THREE.Path();
        holePath.absarc(0, 0, innerRadius, 0, Math.PI * 2, false);
        gearShape.holes.push(holePath);
        
        // Extrude with beveled edges for 3D effect
        const extrudeSettings = {
            depth: thickness,
            bevelEnabled: true,
            bevelSegments: 8,
            steps: 2,
            bevelSize: 3,
            bevelThickness: 3
        };
        
        const gearGeometry = new THREE.ExtrudeGeometry(gearShape, extrudeSettings);
        gearGeometry.center();
        
        // Use same glass material as the operational cubes
        const gearMaterial = new THREE.MeshPhysicalMaterial({
            transmission: 1.0,
            opacity: 1.0,
            thickness: 2.0,
            roughness: 0.0,
            metalness: 0.0,
            ior: 1.52,
            clearcoat: 1.0,
            clearcoatRoughness: 0.0,
            reflectivity: 1.0,
            attenuationColor: new THREE.Color(0.8, 0.9, 1.0),
            attenuationDistance: 1.0,
            dispersion: 0.02,
            transparent: false,
            side: THREE.DoubleSide
        });
        
        // Apply environment map if available
        if (this.environmentMap) {
            gearMaterial.envMap = this.environmentMap;
            gearMaterial.envMapIntensity = 1.0;
        }
        
        const gear = new THREE.Mesh(gearGeometry, gearMaterial);
        gear.rotation.set(0, 0, 0); // Face the user directly
        gear.castShadow = true;
        gear.receiveShadow = true;
        
        sprocketGroup.add(gear);
        sprocketGroup.position.set(0, 0, 0); // Center position
        
        bottomGroup.add(sprocketGroup);
    }
    
    createSprocketGeometry(baseRadius) {
        // Create reusable sprocket geometry based on reference image
        const outerRadius = baseRadius * 1.25;
        const innerRadius = baseRadius * 0.5;
        const thickness = baseRadius * 0.5;
        const teethCount = 8; // 8 teeth like in reference
        
        // Create gear shape with rectangular teeth
        const gearShape = new THREE.Shape();
        
        // Build gear profile with rectangular teeth
        const toothWidth = (Math.PI * 2) / teethCount * 0.4; // Tooth width
        const gapWidth = (Math.PI * 2) / teethCount * 0.6;   // Gap width
        
        for (let i = 0; i < teethCount; i++) {
            const startAngle = i * (Math.PI * 2) / teethCount;
            
            // Tooth profile (rectangular)
            const angles = [
                startAngle,
                startAngle + toothWidth * 0.5,
                startAngle + toothWidth,
                startAngle + toothWidth + gapWidth * 0.5,
                startAngle + toothWidth + gapWidth
            ];
            
            const radii = [
                innerRadius * 1.8, // Base radius
                outerRadius,       // Tooth tip
                outerRadius,       // Tooth tip
                innerRadius * 1.8, // Base radius
                innerRadius * 1.8  // Base radius
            ];
            
            angles.forEach((angle, idx) => {
                const x = Math.cos(angle) * radii[idx];
                const y = Math.sin(angle) * radii[idx];
                
                if (i === 0 && idx === 0) {
                    gearShape.moveTo(x, y);
                } else {
                    gearShape.lineTo(x, y);
                }
            });
        }
        
        // Close the shape
        gearShape.closePath();
        
        // Add center hole
        const holePath = new THREE.Path();
        holePath.absarc(0, 0, innerRadius, 0, Math.PI * 2, false);
        gearShape.holes.push(holePath);
        
        // Extrude with beveled edges for 3D effect
        const extrudeSettings = {
            depth: thickness,
            bevelEnabled: true,
            bevelSegments: 8,
            steps: 2,
            bevelSize: 3,
            bevelThickness: 3
        };
        
        const gearGeometry = new THREE.ExtrudeGeometry(gearShape, extrudeSettings);
        gearGeometry.center();
        
        return gearGeometry;
    }
    
    addGlassLighting() {
        // Advanced lighting setup for ultra-realistic glass materials
        
        // Primary directional light with high intensity for glass
        const keyLight = new THREE.DirectionalLight(0xffffff, 3.0);
        keyLight.position.set(50, 200, 100);
        keyLight.castShadow = true;
        keyLight.shadow.mapSize.width = 4096;
        keyLight.shadow.mapSize.height = 4096;
        keyLight.shadow.camera.near = 0.1;
        keyLight.shadow.camera.far = 500;
        keyLight.shadow.camera.left = -200;
        keyLight.shadow.camera.right = 200;
        keyLight.shadow.camera.top = 200;
        keyLight.shadow.camera.bottom = -200;
        keyLight.shadow.bias = -0.0001;
        this.scene.add(keyLight);
        
        // Fill light from opposite angle for volume
        const fillLight = new THREE.DirectionalLight(0x87ceeb, 2.0);
        fillLight.position.set(-100, 150, 75);
        this.scene.add(fillLight);
        
        // Rim light for glass edge definition
        const rimLight = new THREE.DirectionalLight(0xffffff, 1.5);
        rimLight.position.set(0, 100, -150);
        this.scene.add(rimLight);
        
        // Multiple point lights for glass internal illumination
        const glassPointLight1 = new THREE.PointLight(0x00aaff, 3.0, 300);
        glassPointLight1.position.set(0, 80, 100);
        this.scene.add(glassPointLight1);
        
        const glassPointLight2 = new THREE.PointLight(0xffffff, 2.5, 250);
        glassPointLight2.position.set(-75, 50, -75);
        this.scene.add(glassPointLight2);
        
        const glassPointLight3 = new THREE.PointLight(0x44aaff, 2.0, 200);
        glassPointLight3.position.set(75, 30, 50);
        this.scene.add(glassPointLight3);
        
        // Enhanced ambient light for base visibility
        const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
        this.scene.add(ambientLight);
        
        // Environment mapping for realistic glass reflections
        const pmremGenerator = new THREE.PMREMGenerator(this.renderer);
        pmremGenerator.compileEquirectangularShader();
        
        // Create advanced HDR-like environment texture
        const envTexture = this.createAdvancedEnvironmentTexture();
        if (envTexture) {
            const envMap = pmremGenerator.fromEquirectangular(envTexture).texture;
            this.scene.environment = envMap;
            
            // Store environment map for material assignment
            this.environmentMap = envMap;
            
            envTexture.dispose();
            pmremGenerator.dispose();
        }
    }
    
    createAdvancedEnvironmentTexture() {
        // Create high-quality procedural environment texture for realistic glass reflections
        const canvas = document.createElement('canvas');
        const size = 1024; // Higher resolution for better reflections
        canvas.width = size;
        canvas.height = size;
        const context = canvas.getContext('2d');
        
        // Create complex gradient sky environment with multiple layers
        const skyGradient = context.createLinearGradient(0, 0, 0, size);
        skyGradient.addColorStop(0, '#ffffff'); // Bright white at zenith
        skyGradient.addColorStop(0.1, '#e6f3ff'); // Very light blue
        skyGradient.addColorStop(0.3, '#87ceeb'); // Sky blue
        skyGradient.addColorStop(0.5, '#4682b4'); // Steel blue
        skyGradient.addColorStop(0.7, '#2f4f4f'); // Dark slate gray
        skyGradient.addColorStop(0.9, '#191970'); // Midnight blue
        skyGradient.addColorStop(1, '#000000'); // Black at horizon
        
        context.fillStyle = skyGradient;
        context.fillRect(0, 0, size, size);
        
        // Add bright light sources for sharp reflections
        context.fillStyle = 'rgba(255, 255, 255, 0.9)';
        context.beginPath();
        context.arc(size * 0.2, size * 0.15, size * 0.05, 0, 2 * Math.PI);
        context.fill();
        
        context.beginPath();
        context.arc(size * 0.8, size * 0.25, size * 0.04, 0, 2 * Math.PI);
        context.fill();
        
        // Add cloud formations for complex reflections
        context.fillStyle = 'rgba(255, 255, 255, 0.4)';
        context.beginPath();
        context.ellipse(size * 0.4, size * 0.3, size * 0.15, size * 0.06, Math.PI * 0.2, 0, 2 * Math.PI);
        context.fill();
        
        context.beginPath();
        context.ellipse(size * 0.6, size * 0.4, size * 0.12, size * 0.05, -Math.PI * 0.1, 0, 2 * Math.PI);
        context.fill();
        
        // Add subtle atmospheric bands for realism
        for (let i = 0; i < 5; i++) {
            const y = size * (0.6 + i * 0.08);
            const opacity = 0.1 - i * 0.02;
            context.fillStyle = `rgba(255, 255, 255, ${opacity})`;
            context.fillRect(0, y, size, 2);
        }
        
        // Create texture with advanced mapping
        const texture = new THREE.CanvasTexture(canvas);
        texture.mapping = THREE.EquirectangularReflectionMapping;
        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.flipY = false;
        texture.generateMipmaps = true;
        texture.minFilter = THREE.LinearMipmapLinearFilter;
        texture.magFilter = THREE.LinearFilter;
        
        return texture;
    }
    
    calculateProductionFlowStatus(baseMachineStatuses) {
        // Clone the base statuses to avoid modifying original
        const machineStatuses = baseMachineStatuses.map(machine => ({...machine}));
        
        // Find first faulted machine (production flows left to right)
        let firstFaultIndex = -1;
        for (let i = 0; i < machineStatuses.length; i++) {
            if (machineStatuses[i].status === 'fault') {
                firstFaultIndex = i;
                break;
            }
        }
        
        // If there's a fault, all machines downstream (to the right) become starved
        if (firstFaultIndex !== -1) {
            for (let i = firstFaultIndex + 1; i < machineStatuses.length; i++) {
                if (machineStatuses[i].status === 'operational') {
                    machineStatuses[i].status = 'starved';
                }
            }
        }
        
        return machineStatuses;
    }
    
    animateMachineSprockets() {
        // Animate sprockets based on machine status
        if (this.machineSprockets) {
            this.machineSprockets.forEach(sprocket => {
                const status = sprocket.userData.machineStatus;
                
                if (status === 'operational') {
                    // Slow clockwise rotation for operational machines
                    sprocket.rotation.z += 0.01;
                } else if (status === 'fault' || status === 'starved') {
                    // Stop rotation for fault and starved machines
                    // Sprocket stays at current position
                }
            });
        }
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