/**
 * Three.js Dashboard - Simplified Phase 1
 * Basic working version to test Three.js integration
 */

class SimpleDashboard3D {
    constructor() {
        this.scene = new THREE.Scene();
        this.camera = null;
        this.renderer = null;
        this.container = document.getElementById('threejs-container');
        this.particleSystems = []; // Store particle systems for animation
        
        this.init();
    }
    
    init() {
        // Set scene background - dark navy like image
        this.scene.background = new THREE.Color(0x0a0a15);
        
        // Setup camera for true 3D perspective
        this.camera = new THREE.PerspectiveCamera(
            75, // Wider FOV for better 3D effect
            window.innerWidth / window.innerHeight, 
            0.1, 
            2000
        );
        this.camera.position.set(0, 800, 0); // Look straight down for aligned movement
        this.camera.lookAt(0, 0, 0);
        console.log('Camera positioned at:', this.camera.position);
        
        // Setup renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.container.appendChild(this.renderer.domElement);
        
        // Add grid background
        this.createGridBackground();
        
        // Create simple test geometry
        this.createTestCard();
        
        // Test: Create a simple visible box in center of screen
        // this.createTestBorder(); // Comment out test border
        
        // Start render loop
        this.animate();
        
        // Setup resize handler
        window.addEventListener('resize', () => this.onWindowResize());
        
        // Add interactive camera controls
        this.setupCameraControls();
    }
    
    setupCameraControls() {
        // Add camera position display
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
        positionDisplay.innerHTML = `
            Camera: x=${this.camera.position.x}, y=${this.camera.position.y}, z=${this.camera.position.z}<br>
            <strong>Controls:</strong><br>
            WASD: Move camera<br>
            QE: Up/Down<br>
            RF: Forward/Back<br>
            Space: Reset
        `;
        document.body.appendChild(positionDisplay);
        
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
                case 'r': this.camera.position.set(0, 800, 0); break; // Reset to top-down view
                case ' ': 
                    event.preventDefault();
                    console.log('Current camera position:', this.camera.position);
                    break;
            }
            this.camera.lookAt(0, 0, 0);
            
            // Update display
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
        });
    }
    
    createGridBackground() {
        // Create subtle grid pattern like in the image
        const gridSize = 50;
        const gridWidth = window.innerWidth + gridSize * 2;
        const gridHeight = window.innerHeight + gridSize * 2;
        
        const geometry = new THREE.BufferGeometry();
        const material = new THREE.LineBasicMaterial({ 
            color: 0x1a1a2e, 
            transparent: true, 
            opacity: 0.08  // Much more subtle
        });
        
        const points = [];
        
        // Vertical lines
        for (let i = -gridSize; i <= gridWidth; i += gridSize) {
            points.push(i - window.innerWidth/2, -window.innerHeight/2, -100);
            points.push(i - window.innerWidth/2, window.innerHeight/2, -100);
        }
        
        // Horizontal lines  
        for (let i = -gridSize; i <= gridHeight; i += gridSize) {
            points.push(-window.innerWidth/2, i - window.innerHeight/2, -100);
            points.push(window.innerWidth/2, i - window.innerHeight/2, -100);
        }
        
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
        const grid = new THREE.LineSegments(geometry, material);
        this.scene.add(grid);
    }
    
    createTestBorder() {
        // Create a simple bright green box that should definitely be visible in 3D
        const testGeometry = new THREE.BoxGeometry(200, 100, 80); // Thicker depth
        const testMaterial = new THREE.MeshBasicMaterial({ 
            color: 0x00ff00,
            wireframe: true
        });
        const testBorder = new THREE.Mesh(testGeometry, testMaterial);
        testBorder.position.set(0, 0, 0);
        testBorder.rotation.x = 0.2; // Slight rotation to show 3D
        testBorder.rotation.y = 0.3;
        this.scene.add(testBorder);
        console.log('Test 3D border created - should show depth and perspective');
    }
    
    createTestCard() {
        // Create all 4 KPI cards matching original layout
        this.createKPIRow();
        console.log('KPI row created in Three.js scene');
        console.log('HOLOGRAPHIC EFFECTS ENABLED - Version 2.0');
        console.log('Particles created for each card border');
    }
    
    createKPIRow() {
        // Calculate exact dimensions based on viewport
        const rowHeight = window.innerHeight * 0.25; // 25vh
        const cardWidth = window.innerWidth * 0.18; // Approximately col-3 (20% minus padding)
        const cardHeight = rowHeight * 0.9; // Scale down by 50%
        const padding = window.innerWidth * 0.02; // Padding between cards
        
        // Convert to Three.js units (1 pixel = 1 unit)
        const worldCardWidth = cardWidth;
        const worldCardHeight = cardHeight;
        
        // Make all cards equal width like in the image
        const uniformCardWidth = window.innerWidth * 0.1; // Scale down by 50%
        const colWidths = {
            'col-2': uniformCardWidth,
            'col-3': uniformCardWidth
        };
        
        // Position cards evenly across screen with proper spacing
        const totalCardsWidth = 4 * uniformCardWidth;
        const totalPadding = window.innerWidth - totalCardsWidth;
        const spaceBetween = totalPadding / 5; // Space before, between, and after cards
        const startX = -window.innerWidth / 2 + spaceBetween + uniformCardWidth / 2;
        const yPosition = (window.innerHeight / 4) - (rowHeight / 2); // Drop entire section lower
        
        // KPI data matching original exactly
        const kpiData = [
            { label: 'Availability', value: '95%', cols: 'col-3' },
            { label: 'Performance', value: '88%', cols: 'col-2' },
            { label: 'Quality', value: '98%', cols: 'col-2' },
            { label: 'Overall OEE', value: '82%', cols: 'col-3' }
        ];
        
        let currentX = startX;
        
        kpiData.forEach((kpi, index) => {
            const cardGroup = new THREE.Group();
            const thisCardWidth = colWidths[kpi.cols];
            
            // Holographic card background with perspective
            const cardGeometry = new THREE.PlaneGeometry(thisCardWidth, worldCardHeight);
            const cardMaterial = new THREE.MeshBasicMaterial({ 
                color: 0x1a1a2e,
                side: THREE.DoubleSide,
                transparent: true,
                opacity: 0.6
            });
            const cardMesh = new THREE.Mesh(cardGeometry, cardMaterial);
            
            // Add holographic tilt - dramatic 3D perspective
            cardMesh.rotation.x = -0.3; // More dramatic tilt toward viewer
            cardMesh.rotation.y = (index - 1.5) * 0.08; // More angle variation per card
            cardMesh.position.z = Math.sin(index) * 20; // Varying depths
            
            // Create solid rectangular border frame like red boxes in image
            const borderWidth = 8; // Much thicker to ensure visibility
            const cardColors = [0x00ff88, 0x0088ff, 0x8800ff, 0xff4444];
            console.log(`Creating border for card ${index} with color:`, cardColors[index]);
            
            // Top border strip
            const topBorderGeo = new THREE.PlaneGeometry(thisCardWidth + 4, borderWidth);
            const topBorderMat = new THREE.MeshBasicMaterial({ color: cardColors[index], transparent: false });
            const topBorder = new THREE.Mesh(topBorderGeo, topBorderMat);
            topBorder.position.set(0, worldCardHeight/2 + borderWidth/2, 10); // Move much closer to camera
            // No rotation to ensure visibility
            console.log(`Top border created for card ${index}`);
            
            // Bottom border strip  
            const bottomBorderGeo = new THREE.PlaneGeometry(thisCardWidth + 4, borderWidth);
            const bottomBorderMat = new THREE.MeshBasicMaterial({ color: cardColors[index], transparent: false });
            const bottomBorder = new THREE.Mesh(bottomBorderGeo, bottomBorderMat);
            bottomBorder.position.set(0, -worldCardHeight/2 - borderWidth/2, 10);
            
            // Left border strip
            const leftBorderGeo = new THREE.PlaneGeometry(borderWidth, worldCardHeight);
            const leftBorderMat = new THREE.MeshBasicMaterial({ color: cardColors[index], transparent: false });
            const leftBorder = new THREE.Mesh(leftBorderGeo, leftBorderMat);
            leftBorder.position.set(-thisCardWidth/2 - borderWidth/2, 0, 10);
            
            // Right border strip
            const rightBorderGeo = new THREE.PlaneGeometry(borderWidth, worldCardHeight);
            const rightBorderMat = new THREE.MeshBasicMaterial({ color: cardColors[index], transparent: false });
            const rightBorder = new THREE.Mesh(rightBorderGeo, rightBorderMat);
            rightBorder.position.set(thisCardWidth/2 + borderWidth/2, 0, 10);
            
            // Add animated scan line effect
            const scanGeometry = new THREE.PlaneGeometry(thisCardWidth, 20);
            const scanMaterial = new THREE.MeshBasicMaterial({
                color: cardColors[index],
                transparent: true,
                opacity: 0.4
            });
            const scanMesh = new THREE.Mesh(scanGeometry, scanMaterial);
            scanMesh.position.set(0, 0, 0.01);
            scanMesh.rotation.x = -0.3;
            scanMesh.rotation.y = (index - 1.5) * 0.08;
            
            cardGroup.add(cardMesh);
            cardGroup.add(topBorder);
            cardGroup.add(bottomBorder);
            cardGroup.add(leftBorder);
            cardGroup.add(rightBorder);
            cardGroup.add(scanMesh);
            
            // Add particle effects around border
            this.createBorderParticles(cardGroup, thisCardWidth, worldCardHeight, cardColors[index], index);
            
            // Store scan line for animation
            cardGroup.userData.scanLine = scanMesh;
            cardGroup.userData.animPhase = index * 0.5;
            cardGroup.userData.particles = [];
            
            // Position each card
            cardGroup.position.set(currentX, yPosition, 0);
            this.scene.add(cardGroup);
            
            // Create HTML overlay for text and sparklines
            this.createKPIContent(kpi, index, currentX, yPosition, thisCardWidth, worldCardHeight);
            
            // Move to next card position
            currentX += uniformCardWidth + spaceBetween;
        });
        
        // Load real data after cards are created  
        setTimeout(() => this.loadRealData(), 1000);
        
        // Set up automatic updates like original
        setInterval(() => this.loadRealData(), 5000);
    }
    
    createBorderParticles(cardGroup, cardWidth, cardHeight, color, index) {
        // Create floating particles around card border
        const particleCount = 20;
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        
        for (let i = 0; i < particleCount; i++) {
            // Position particles around card perimeter
            const angle = (i / particleCount) * Math.PI * 2;
            const radius = Math.max(cardWidth, cardHeight) / 2 + 20;
            
            positions[i * 3] = Math.cos(angle) * radius + (Math.random() - 0.5) * 40;
            positions[i * 3 + 1] = Math.sin(angle) * radius + (Math.random() - 0.5) * 40;
            positions[i * 3 + 2] = (Math.random() - 0.5) * 50;
            
            // Set particle color
            const r = ((color >> 16) & 255) / 255;
            const g = ((color >> 8) & 255) / 255;
            const b = (color & 255) / 255;
            
            colors[i * 3] = r;
            colors[i * 3 + 1] = g;
            colors[i * 3 + 2] = b;
        }
        
        const particleGeometry = new THREE.BufferGeometry();
        particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        particleGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        
        const particleMaterial = new THREE.PointsMaterial({
            size: 3,
            transparent: true,
            opacity: 0.6,
            vertexColors: true,
            blending: THREE.AdditiveBlending
        });
        
        const particles = new THREE.Points(particleGeometry, particleMaterial);
        particles.rotation.x = -0.3;
        particles.rotation.y = (index - 1.5) * 0.08;
        
        cardGroup.add(particles);
        
        // Store in main array for animation
        this.particleSystems.push({
            particles: particles,
            phase: index * 0.5,
            positions: positions
        });
    }
    
    createKPIContent(kpi, index, worldX, worldY, cardWidth, cardHeight) {
        // Convert Three.js world position to screen position using proper projection
        const worldPosition = new THREE.Vector3(worldX, worldY, 0);
        const screenPosition = worldPosition.clone().project(this.camera);
        
        // Convert normalized device coordinates to screen pixels
        const canvasHalfWidth = window.innerWidth / 2;
        const canvasHalfHeight = window.innerHeight / 2;
        
        const screenX = (screenPosition.x * canvasHalfWidth) + canvasHalfWidth - (cardWidth / 2);
        const screenY = -(screenPosition.y * canvasHalfHeight) + canvasHalfHeight - (cardHeight / 2);
        
        console.log(`Card ${index} projection: world(${worldX},${worldY}) -> screen(${screenX},${screenY})`);
        
        // Create container div for this KPI
        const kpiContainer = document.createElement('div');
        kpiContainer.style.position = 'absolute';
        kpiContainer.style.left = screenX + 'px';
        kpiContainer.style.top = screenY + 'px';
        kpiContainer.style.width = (cardWidth - 40) + 'px'; // Account for padding
        kpiContainer.style.height = (cardHeight - 40) + 'px';
        kpiContainer.style.display = 'flex';
        kpiContainer.style.flexDirection = 'column';
        kpiContainer.style.justifyContent = 'flex-start'; // Start from top
        kpiContainer.style.padding = '20px';
        kpiContainer.style.boxSizing = 'border-box';
        kpiContainer.style.pointerEvents = 'none';
        
        // Header with label - small, upper-left positioned
        const headerDiv = document.createElement('div');
        headerDiv.style.color = '#00ffff';
        headerDiv.style.fontSize = '11px';
        headerDiv.style.fontWeight = '600';
        headerDiv.style.textTransform = 'uppercase';
        headerDiv.style.fontFamily = 'system-ui';
        headerDiv.style.letterSpacing = '1px';
        headerDiv.style.textAlign = 'left';
        headerDiv.style.marginBottom = '15px';
        headerDiv.style.textShadow = '0 0 8px #00ffff';
        headerDiv.innerHTML = kpi.label;
        
        // Main value - large glowing cyan, positioned in upper area
        const valueDiv = document.createElement('div');
        valueDiv.style.color = '#00ffff';
        valueDiv.style.fontSize = '2.8rem'; // Smaller to match target
        valueDiv.style.fontWeight = '700';
        valueDiv.style.lineHeight = '1';
        valueDiv.style.fontFamily = 'system-ui';
        valueDiv.style.textAlign = 'center';
        valueDiv.style.textShadow = '0 0 15px #00ffff, 0 0 30px #00ffff';
        valueDiv.style.marginBottom = '8px';
        valueDiv.innerHTML = kpi.value;
        valueDiv.className = 'kpi-value';
        valueDiv.setAttribute('data-kpi', kpi.label);
        
        // Secondary label below value - smaller and dimmer
        const secondaryDiv = document.createElement('div');
        secondaryDiv.style.color = '#00ffff';
        secondaryDiv.style.fontSize = '12px';
        secondaryDiv.style.fontWeight = '400';
        secondaryDiv.style.textAlign = 'center';
        secondaryDiv.style.fontFamily = 'system-ui';
        secondaryDiv.style.textShadow = '0 0 8px #00ffff';
        secondaryDiv.style.marginBottom = '20px';
        secondaryDiv.style.opacity = '0.8';
        secondaryDiv.innerHTML = kpi.label.toUpperCase() + (kpi.label !== 'Overall OEE' ? ' %' : '');
        
        // Sparkline area - positioned in middle section
        const sparklineDiv = document.createElement('div');
        sparklineDiv.style.height = '50px';
        sparklineDiv.style.position = 'relative';
        sparklineDiv.style.marginBottom = '20px';
        sparklineDiv.style.background = 'rgba(20, 20, 35, 0.5)';
        sparklineDiv.style.borderRadius = '4px';
        sparklineDiv.style.padding = '5px';
        
        // Canvas for sparkline
        const canvas = document.createElement('canvas');
        canvas.width = cardWidth - 50;
        canvas.height = 30;
        canvas.style.width = '100%';
        canvas.style.height = '30px';
        canvas.id = `${kpi.label.toLowerCase()}-sparkline-threejs`;
        
        // Mini indicators
        const indicatorDiv = document.createElement('div');
        indicatorDiv.style.position = 'absolute';
        indicatorDiv.style.bottom = '0';
        indicatorDiv.style.right = '10px';
        indicatorDiv.style.fontSize = '12px';
        indicatorDiv.style.color = '#6c757d';
        
        // Add trend indicators matching target image
        if (kpi.label === 'Availability') {
            indicatorDiv.innerHTML = '<span>∇7 2v</span>';
        } else if (kpi.label === 'Performance') {
            indicatorDiv.innerHTML = '<span>-1.2</span>';
        } else if (kpi.label === 'Quality') {
            indicatorDiv.innerHTML = '<span>+0.5</span>';
        } else if (kpi.label === 'Overall OEE') {
            indicatorDiv.innerHTML = '<span>+1.5</span>';
        }
        
        sparklineDiv.appendChild(canvas);
        sparklineDiv.appendChild(indicatorDiv);
        
        // Circular progress dial - smaller, at bottom
        const dialDiv = document.createElement('div');
        dialDiv.style.height = '50px';
        dialDiv.style.display = 'flex';
        dialDiv.style.justifyContent = 'center';
        dialDiv.style.alignItems = 'flex-end';
        dialDiv.style.marginTop = 'auto'; // Push to bottom
        
        const dialCanvas = document.createElement('canvas');
        dialCanvas.width = 40;
        dialCanvas.height = 40;
        dialCanvas.style.width = '40px';
        dialCanvas.style.height = '40px';
        dialCanvas.id = `${kpi.label.toLowerCase()}-dial-threejs`;
        
        dialDiv.appendChild(dialCanvas);
        
        // Assemble the card with proper hierarchy
        kpiContainer.appendChild(headerDiv);
        kpiContainer.appendChild(valueDiv);
        kpiContainer.appendChild(secondaryDiv);
        kpiContainer.appendChild(sparklineDiv);
        kpiContainer.appendChild(dialDiv);
        
        document.body.appendChild(kpiContainer);
        
        // Initialize sparkline chart and progress dial
        this.initSparkline(canvas, kpi.label);
        this.initProgressDial(dialCanvas, kpi.label, parseFloat(kpi.value));
    }
    
    // Connect to real API data
    async loadRealData() {
        try {
            const response = await fetch('/api/current-metrics/');
            const data = await response.json();
            this.updateWithRealData(data);
        } catch (error) {
            console.log('Using fallback data:', error);
        }
    }
    
    updateWithRealData(apiData) {
        console.log('Updating with API data:', apiData);
        
        // Update KPI values from API
        if (apiData.availability) {
            const availValue = document.querySelector('[data-kpi="Availability"]');
            if (availValue) {
                availValue.innerHTML = apiData.availability.toFixed(1) + '%';
                console.log('Updated Availability to:', apiData.availability.toFixed(1) + '%');
            }
        }
        if (apiData.performance) {
            const perfValue = document.querySelector('[data-kpi="Performance"]');
            if (perfValue) {
                perfValue.innerHTML = apiData.performance.toFixed(1) + '%';
                console.log('Updated Performance to:', apiData.performance.toFixed(1) + '%');
            }
        }
        if (apiData.quality) {
            const qualValue = document.querySelector('[data-kpi="Quality"]');
            if (qualValue) {
                qualValue.innerHTML = apiData.quality.toFixed(1) + '%';
                console.log('Updated Quality to:', apiData.quality.toFixed(1) + '%');
            }
        }
        if (apiData.oee) {
            const oeeValue = document.querySelector('[data-kpi="Overall OEE"]');
            if (oeeValue) {
                oeeValue.innerHTML = apiData.oee.toFixed(1) + '%';
                console.log('Updated OEE to:', apiData.oee.toFixed(1) + '%');
            }
        }
    }
    
    initSparkline(canvas, label) {
        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        
        // Clear canvas with dark background
        ctx.fillStyle = '#0f1419';
        ctx.fillRect(0, 0, width, height);
        
        // Exact same data as original dashboard
        const sparklineData = {
            'Availability': [88, 90, 92, 89, 93, 91, 92.5],
            'Performance': [92, 88, 90, 87, 89, 90, 89.1],
            'Quality': [94, 96, 95, 97, 95, 96, 95.8],
            'Overall OEE': [82, 84, 86, 83, 87, 85, 85.3]
        };
        
        const data = sparklineData[label] || [];
        if (data.length === 0) return;
        
        const padding = 4;
        const chartWidth = width - (padding * 2);
        const chartHeight = height - (padding * 2);
        
        // Find min/max for scaling
        const min = Math.min(...data);
        const max = Math.max(...data);
        const range = max - min || 1;
        
        // Calculate points
        const points = data.map((value, index) => ({
            x: padding + (index * chartWidth / (data.length - 1)),
            y: padding + chartHeight - ((value - min) / range * chartHeight)
        }));
        
        // Draw glowing line - colors matching image exactly
        const colors = {
            'Availability': '#00ff88',
            'Performance': '#0088ff', 
            'Quality': '#8800ff',
            'Overall OEE': '#ff4444'  // Red for warning
        };
        
        ctx.strokeStyle = colors[label] || '#00ff88';
        ctx.lineWidth = 2;
        ctx.shadowColor = colors[label] || '#00ff88';
        ctx.shadowBlur = 8;
        
        ctx.beginPath();
        points.forEach((point, index) => {
            if (index === 0) {
                ctx.moveTo(point.x, point.y);
            } else {
                ctx.lineTo(point.x, point.y);
            }
        });
        ctx.stroke();
        
        // Add gradient fill
        ctx.shadowBlur = 0;
        const gradient = ctx.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, colors[label] + '40'); // Semi-transparent
        gradient.addColorStop(1, colors[label] + '00'); // Transparent
        
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.moveTo(points[0].x, height);
        points.forEach(point => ctx.lineTo(point.x, point.y));
        ctx.lineTo(points[points.length - 1].x, height);
        ctx.closePath();
        ctx.fill();
    }
    
    initProgressDial(canvas, label, percentage) {
        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = 15; // Smaller to match image
        
        // Clear canvas
        ctx.clearRect(0, 0, width, height);
        
        // Colors matching the image - OEE is red/warning
        const colors = {
            'Availability': '#00ff88',
            'Performance': '#0088ff', 
            'Quality': '#8800ff',
            'Overall OEE': '#ff4444'  // Red for warning/critical
        };
        
        const color = colors[label] || '#00ff88';
        
        // Background ring - thinner like in image
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
        ctx.strokeStyle = '#2a2a3e';
        ctx.lineWidth = 1;
        ctx.stroke();
        
        // Progress ring - thin glowing line
        const progress = (percentage / 100) * 2 * Math.PI;
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, -Math.PI / 2, -Math.PI / 2 + progress);
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.shadowColor = color;
        ctx.shadowBlur = 5;
        ctx.stroke();
        
        // Small center dot
        ctx.shadowBlur = 0;
        ctx.beginPath();
        ctx.arc(centerX, centerY, 2, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.fill();
    }
    
    onWindowResize() {
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        console.log('Camera resized, aspect:', this.camera.aspect);
    }
    
    animate() {
        requestAnimationFrame(() => this.animate());
        
        // Animate holographic effects using stored particle systems
        const time = Date.now() * 0.001;
        
        // Animate particles directly
        this.particleSystems.forEach((system, index) => {
            const positions = system.positions;
            const particles = system.particles;
            const phase = system.phase;
            
            for (let i = 0; i < positions.length; i += 3) {
                // Create visible floating movement
                positions[i] += Math.cos(time + i + phase) * 2.0; // X movement
                positions[i + 1] += Math.sin(time * 1.2 + i + phase) * 1.5; // Y movement
                positions[i + 2] += Math.sin(time * 2 + i + phase) * 3.0; // Z movement
            }
            
            particles.geometry.attributes.position.needsUpdate = true;
            
            // Animate particle properties
            particles.material.opacity = 0.7 + Math.sin(time * 2 + phase) * 0.3;
            particles.material.size = 4 + Math.sin(time * 3 + phase) * 3;
        });
        
        // Animate scan lines
        this.scene.traverse((object) => {
            if (object.userData.scanLine) {
                const scanLine = object.userData.scanLine;
                const phase = object.userData.animPhase;
                
                // Move scan line up and down
                scanLine.position.y = Math.sin(time + phase) * 100;
                scanLine.material.opacity = 0.3 + Math.sin(time * 2 + phase) * 0.2;
            }
        });
        
        this.renderer.render(this.scene, this.camera);
    }
}

// Initialize when page loads
let dashboard = null;

document.addEventListener('DOMContentLoaded', function() {
    console.log('Three.js version:', THREE.REVISION);
    console.log('Initializing Simple Three.js Dashboard');
    
    try {
        dashboard = new SimpleDashboard3D();
        console.log('Three.js dashboard initialized successfully');
    } catch (error) {
        console.error('Failed to initialize Three.js dashboard:', error);
    }
});