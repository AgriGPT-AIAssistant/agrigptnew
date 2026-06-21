'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Sprout, CloudSun, LineChart, Brain } from 'lucide-react';

export const AuthHero: React.FC = () => {
  const features = [
    { icon: Brain, label: 'Advanced Agronomy Model', desc: 'Custom RAG pipeline tuned for regional crops.' },
    { icon: CloudSun, label: 'Weather Intelligence', desc: 'Real-time farm advisory based on local humidity & rain.' },
    { icon: LineChart, label: 'Market Insights & Trends', desc: 'Strategic market intelligence to maximize mandi pricing.' },
  ];

  return (
    <div className="relative flex flex-col justify-between h-full p-8 md:p-16 text-foreground z-10 select-none">
      {/* Top Header Logo */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
        className="flex items-center gap-3"
      >
        <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 text-primary shadow-[0_0_20px_rgba(27,67,50,0.08)]">
          <Sprout className="w-5 h-5" />
        </div>
        <span className="text-xl font-bold tracking-tight text-foreground font-mono">
          Agri<span className="text-primary">GPT</span>
        </span>
      </motion.div>

      {/* Center AI Agricultural Illustration */}
      <div className="flex-1 flex flex-col justify-center items-center py-12">
        <div className="relative w-full max-w-[360px] aspect-square flex items-center justify-center">
          {/* Outer Rotating Halo */}
          <motion.div
            className="absolute inset-0 rounded-full border border-primary/5 border-dashed"
            animate={{ rotate: 360 }}
            transition={{ duration: 40, repeat: Infinity, ease: 'linear' }}
          />

          {/* Inner Rotating Orbit 1 */}
          <motion.div
            className="absolute w-[80%] h-[80%] rounded-full border border-primary/10"
            animate={{ rotate: -360 }}
            transition={{ duration: 30, repeat: Infinity, ease: 'linear' }}
          />

          {/* Glowing Center Hub */}
          <div className="absolute w-40 h-40 rounded-full bg-primary/5 border border-primary/20 flex items-center justify-center shadow-[0_0_50px_rgba(27,67,50,0.04)] backdrop-blur-sm">
            <motion.div
              animate={{ 
                scale: [0.95, 1.05, 0.95],
                boxShadow: [
                  '0 0 20px rgba(27,67,50,0.05)',
                  '0 0 40px rgba(27,67,50,0.1)',
                  '0 0 20px rgba(27,67,50,0.05)'
                ]
              }}
              transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
              className="w-28 h-28 rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center"
            >
              <Sprout className="w-12 h-12 text-primary" />
            </motion.div>
          </div>

          {/* Orbiting Icons */}
          {[
            { Icon: Brain, angle: 0, delay: 0 },
            { Icon: CloudSun, angle: 120, delay: 1.5 },
            { Icon: LineChart, angle: 240, delay: 3 }
          ].map(({ Icon, angle, delay }, idx) => {
            const radius = 130;
            const rad = (angle * Math.PI) / 180;
            const x = radius * Math.cos(rad);
            const y = radius * Math.sin(rad);

            return (
              <motion.div
                key={idx}
                className="absolute w-10 h-10 rounded-lg bg-card border border-border flex items-center justify-center text-foreground/80 shadow-md backdrop-blur-md"
                style={{ x, y }}
                animate={{
                  y: [y, y - 10, y],
                }}
                transition={{
                  duration: 4,
                  delay,
                  repeat: Infinity,
                  ease: 'easeInOut',
                }}
                whileHover={{
                  scale: 1.1,
                  borderColor: 'rgba(27, 67, 50, 0.3)',
                  color: '#1B4332',
                }}
              >
                <Icon className="w-5 h-5" />
              </motion.div>
            );
          })}
        </div>

        {/* Tagline & Subtext */}
        <div className="text-center max-w-md mt-8 space-y-3">
          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl"
          >
            AI-Powered Agricultural Intelligence
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="text-sm text-muted-foreground leading-relaxed"
          >
            Expert crop guidance, weather intelligence, market insights, and farming recommendations powered by advanced AI.
          </motion.p>
        </div>
      </div>

      {/* Footer Feature Details */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8, delay: 0.4 }}
        className="hidden lg:grid grid-cols-3 gap-6 border-t border-border pt-8 mt-auto"
      >
        {features.map(({ icon: Icon, label, desc }, idx) => (
          <div key={idx} className="space-y-1">
            <div className="flex items-center gap-2 text-foreground text-xs font-semibold">
              <Icon className="w-3.5 h-3.5 text-primary" />
              {label}
            </div>
            <p className="text-[11px] text-muted-foreground leading-normal">{desc}</p>
          </div>
        ))}
      </motion.div>
    </div>
  );
};
