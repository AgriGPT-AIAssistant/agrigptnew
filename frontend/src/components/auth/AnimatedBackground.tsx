'use client';

import React from 'react';
import { motion } from 'framer-motion';

export const AnimatedBackground: React.FC = () => {
  return (
    <div className="absolute inset-0 overflow-hidden bg-bg-luxury z-0 select-none pointer-events-none">
      {/* Dynamic Glow Sphere 1 */}
      <motion.div
        className="absolute w-[500px] h-[500px] rounded-full bg-accent-luxury/10 blur-[120px] -top-40 -left-40"
        animate={{
          x: [0, 80, -40, 0],
          y: [0, -60, 40, 0],
          scale: [1, 1.15, 0.9, 1],
        }}
        transition={{
          duration: 25,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* Dynamic Glow Sphere 2 (Sage Green/Ivory) */}
      <motion.div
        className="absolute w-[600px] h-[600px] rounded-full bg-[#708D81]/15 blur-[150px] -bottom-60 -right-60"
        animate={{
          x: [0, -100, 50, 0],
          y: [0, 80, -50, 0],
          scale: [1, 0.85, 1.1, 1],
        }}
        transition={{
          duration: 30,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* Dynamic Glow Sphere 3 (Warm Ivory) */}
      <motion.div
        className="absolute w-[400px] h-[400px] rounded-full bg-[#F2EFE9]/40 blur-[100px] top-1/2 left-1/3 -translate-y-1/2 -translate-x-1/2"
        animate={{
          scale: [0.9, 1.1, 0.9],
          opacity: [0.3, 0.6, 0.3],
        }}
        transition={{
          duration: 15,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* Premium Fine Grain Texture Overlay */}
      <div
        className="absolute inset-0 opacity-[0.03] mix-blend-overlay"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
        }}
      />

      {/* Grid Pattern Layer (Slightly dark grid lines for light background) */}
      <div 
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(to right, rgba(27, 67, 50, 0.15) 1px, transparent 1px), linear-gradient(to bottom, rgba(27, 67, 50, 0.15) 1px, transparent 1px)`,
          backgroundSize: '40px 40px',
        }}
      />
    </div>
  );
};
