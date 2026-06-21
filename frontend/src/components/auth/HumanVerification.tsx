'use client';

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { RotateCw, CheckCircle2, AlertCircle, Shield } from 'lucide-react';

interface HumanVerificationProps {
  onVerifySuccess: () => void;
  sitekey?: string; // Kept for Turnstile API architecture compatibility
}

export const HumanVerification: React.FC<HumanVerificationProps> = ({
  onVerifySuccess,
}) => {
  const [captchaCode, setCaptchaCode] = useState('');
  const [userInput, setUserInput] = useState('');
  const [verificationState, setVerificationState] = useState<'idle' | 'failed' | 'verified'>('idle');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Generate random 6-8 character alphanumeric code (excluding confusing characters)
  const generateCode = (): string => {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    const length = Math.floor(Math.random() * 3) + 6; // 6 to 8 characters
    let code = '';
    for (let i = 0; i < length; i++) {
      code += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return code;
  };

  // Draw the code on the canvas with distortions, lines, and noise dots
  const drawCaptcha = (code: string) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear and set background
    ctx.fillStyle = '#F2EFE9'; // Warm Ivory
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // 1. Draw background noise lines
    for (let i = 0; i < 5; i++) {
      ctx.strokeStyle = `rgba(27, 67, 50, ${Math.random() * 0.15 + 0.05})`; // Farmer Green
      ctx.lineWidth = Math.random() * 2 + 1;
      ctx.beginPath();
      ctx.moveTo(Math.random() * canvas.width, Math.random() * canvas.height);
      ctx.lineTo(Math.random() * canvas.width, Math.random() * canvas.height);
      ctx.stroke();
    }

    // 2. Draw background grid/dots
    for (let i = 0; i < 40; i++) {
      ctx.fillStyle = `rgba(27, 67, 50, ${Math.random() * 0.08})`; // Farmer Green noise
      ctx.beginPath();
      ctx.arc(
        Math.random() * canvas.width,
        Math.random() * canvas.height,
        Math.random() * 2 + 0.5,
        0,
        Math.PI * 2
      );
      ctx.fill();
    }

    // 3. Draw text characters with rotation, translation, and scale distortions
    ctx.textBaseline = 'middle';
    const charWidth = (canvas.width - 20) / code.length;
    
    for (let i = 0; i < code.length; i++) {
      const char = code[i];
      const x = 15 + charWidth * i + (Math.random() * 4 - 2);
      const y = canvas.height / 2 + (Math.random() * 8 - 4);
      
      ctx.save();
      ctx.translate(x + 5, y);
      
      // Random rotation: -20 to +20 degrees
      const angle = ((Math.random() * 40 - 20) * Math.PI) / 180;
      ctx.rotate(angle);
      
      // Font variations
      const fontSize = Math.floor(Math.random() * 4) + 20; // 20px - 23px
      ctx.font = `bold ${fontSize}px var(--font-geist-mono), Courier New, monospace`;
      
      // Draw character with gradient/color variation (Charcoal and Farmer Green)
      ctx.fillStyle = Math.random() > 0.4 ? '#1B4332' : '#2C3539';
      ctx.fillText(char, -8, 0);
      
      ctx.restore();
    }

    // 4. Draw foreground noise lines (crossing characters)
    for (let i = 0; i < 3; i++) {
      ctx.strokeStyle = `rgba(27, 67, 50, ${Math.random() * 0.2 + 0.1})`;
      ctx.lineWidth = Math.random() * 1.5 + 0.5;
      ctx.beginPath();
      ctx.moveTo(Math.random() * canvas.width, Math.random() * canvas.height);
      ctx.lineTo(Math.random() * canvas.width, Math.random() * canvas.height);
      ctx.stroke();
    }
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    const newCode = generateCode();
    setCaptchaCode(newCode);
    setUserInput('');
    if (verificationState === 'failed') {
      setVerificationState('idle');
    }
    
    setTimeout(() => {
      setIsRefreshing(false);
    }, 600);
  };

  const handleVerify = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    
    if (userInput.trim().toUpperCase() === captchaCode) {
      setVerificationState('verified');
      // Store verification token/state in sessionStorage for security layer
      try {
        sessionStorage.setItem('agri_auth_verified', 'true');
      } catch (err) {
        console.error('Session storage writing failed:', err);
      }
      onVerifySuccess();
    } else {
      setVerificationState('failed');
      setUserInput('');
      // Regenerate CAPTCHA immediately on failure as requested
      const newCode = generateCode();
      setCaptchaCode(newCode);
    }
  };

  // Initial code generation
  useEffect(() => {
    const code = generateCode();
    setCaptchaCode(code);
  }, []);

  // Redraw canvas whenever code changes
  useEffect(() => {
    if (captchaCode) {
      drawCaptcha(captchaCode);
    }
  }, [captchaCode]);

  return (
    <div className="w-full select-none space-y-4">
      <div className="relative p-5 bg-card border border-border rounded-2xl backdrop-blur-md overflow-hidden transition-all duration-300">
        {/* Ambient top light */}
        <div className="absolute top-0 inset-x-0 h-[1px] bg-gradient-to-r from-transparent via-primary/10 to-transparent" />

        <AnimatePresence mode="wait">
          {verificationState !== 'verified' ? (
            <motion.div
              key="verification-form"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-4"
            >
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-secondary border border-border text-muted-foreground">
                  <Shield className="w-4 h-4 text-primary" />
                </div>
                <div className="flex flex-col">
                  <span className="text-sm font-medium text-foreground">Security Check</span>
                  <span className="text-[11px] text-muted-foreground">Verify you are human to continue</span>
                </div>
              </div>

              {/* CAPTCHA Display Canvas */}
              <div className="flex items-center justify-between gap-3 bg-secondary/40 p-2 rounded-xl border border-border">
                <div className="relative rounded-lg overflow-hidden border border-border/50">
                  {/* Subtle CSS blur filter layer for canvas */}
                  <canvas
                    ref={canvasRef}
                    width={200}
                    height={55}
                    className="block blur-[0.4px] opacity-90"
                  />
                </div>

                {/* Refresh Action */}
                <button
                  type="button"
                  onClick={handleRefresh}
                  disabled={isRefreshing}
                  className="flex items-center justify-center w-10 h-10 rounded-xl bg-card border border-border hover:border-primary/30 text-muted-foreground hover:text-primary transition-all cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-primary"
                >
                  <RotateCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                </button>
              </div>

              {/* Input Form */}
              <form onSubmit={handleVerify} className="flex gap-2">
                <input
                  type="text"
                  maxLength={8}
                  value={userInput}
                  onChange={(e) => setUserInput(e.target.value.toUpperCase())}
                  placeholder="Enter code above"
                  className={`flex-1 h-10 px-4 bg-card border rounded-xl text-sm font-mono tracking-widest text-foreground uppercase outline-none transition-all ${
                    verificationState === 'failed'
                      ? 'border-rose-500/50 focus:border-rose-500 focus:ring-1 focus:ring-rose-500/50'
                      : 'border-border focus:border-primary/50 focus:ring-1 focus:ring-primary/20'
                  }`}
                  aria-label="Enter security code"
                />
                
                <button
                  type="submit"
                  disabled={userInput.trim().length < 5}
                  className={`px-4 h-10 rounded-xl text-xs font-semibold tracking-wide transition-all border outline-none select-none ${
                    userInput.trim().length >= 5
                      ? 'bg-primary/10 border-primary/30 text-primary hover:bg-primary/20 hover:border-primary/50 cursor-pointer transform active:scale-95'
                      : 'bg-secondary/40 border-border text-muted-foreground/40 cursor-not-allowed'
                  }`}
                >
                  Verify
                </button>
              </form>

              {/* Verification Message */}
              <AnimatePresence>
                {verificationState === 'failed' && (
                  <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="flex items-center gap-2 text-xs text-rose-600 bg-rose-50 border border-rose-100 p-2.5 rounded-xl"
                  >
                    <AlertCircle className="w-4 h-4 shrink-0 text-rose-500" />
                    <span>Incorrect code. CAPTCHA regenerated.</span>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ) : (
            <motion.div
              key="verified-status"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex flex-col items-center justify-center py-4 space-y-3"
            >
              <motion.div
                initial={{ scale: 0.8 }}
                animate={{ scale: [0.8, 1.1, 1] }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
                className="w-12 h-12 rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center text-primary shadow-[0_0_20px_rgba(27,67,50,0.15)]"
              >
                <CheckCircle2 className="w-6 h-6" />
              </motion.div>
              <div className="text-center space-y-1">
                <span className="text-sm font-semibold text-foreground block">Security Cleared</span>
                <span className="text-xs text-muted-foreground leading-normal">
                  Google authentication has been unlocked
                </span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};
