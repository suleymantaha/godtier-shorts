import { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Stars, Sparkles, OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import { useThemeStore } from '../store/useThemeStore';

const Starfield = ({ isLight }: { isLight: boolean }) => {
    const starsRef = useRef<THREE.Group>(null);

    useFrame((state, delta) => {
        if (starsRef.current) {
            // Yavaşça yıldızları döndür (uzayda süzülme hissi)
            starsRef.current.rotation.y -= delta * (isLight ? 0.005 : 0.02);
            starsRef.current.rotation.x -= delta * (isLight ? 0.003 : 0.01);
            
            // Hafif bir yukarı aşağı salınım
            starsRef.current.position.y = Math.sin(state.clock.elapsedTime * 0.5) * 0.5;
        }
    });

    return (
        <group ref={starsRef}>
            {isLight ? (
                <Sparkles
                    count={2000}
                    scale={100}
                    size={2}
                    speed={0.05}
                    opacity={0.5}
                    color="#1e293b" // Koyu Gri / Lacivert toz
                />
            ) : (
                <Stars
                    radius={100}      
                    depth={50}        
                    count={5000}      
                    factor={4}        
                    saturation={1}    
                    fade              
                    speed={1}         
                />
            )}
            {isLight && (
                 <Sparkles
                    count={800}
                    scale={80}
                    size={3}
                    speed={0.03}
                    opacity={0.4}
                    color="#09090b" // Simsiyah toz
                />
            )}
        </group>
    );
};

export default function ThreeCanvas() {
    const { theme } = useThemeStore();
    const isLight = theme === 'light';
    const bgColor = isLight ? '#f8fafc' : '#05050A';

    return (
        <div className="fixed inset-0 -z-50 pointer-events-none transition-colors duration-700" style={{ backgroundColor: bgColor }}>
            <Canvas camera={{ position: [0, 0, 1] }}>
                <ambientLight intensity={isLight ? 1 : 0.5} />
                <PointLightWithColor position={[10, 10, 10]} color={isLight ? "#f1f5f9" : "#00F0FF"} intensity={isLight ? 2 : 1} />
                <PointLightWithColor position={[-10, -10, -10]} color={isLight ? "#e2e8f0" : "#8A2BE2"} intensity={isLight ? 2 : 1} />
                <Starfield isLight={isLight} />
                
                <OrbitControls 
                    enableZoom={false} 
                    enablePan={false} 
                    enableRotate={false} 
                />
            </Canvas>
        </div>
    );
}

// PointLight helper component
const PointLightWithColor = ({ position, color, intensity }: { position: [number, number, number], color: string, intensity: number }) => {
    return (
        <pointLight position={position} intensity={intensity} color={new THREE.Color(color)} />
    );
};
