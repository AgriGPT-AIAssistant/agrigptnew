'use client';

import React, { useState } from 'react';
import { motion, Variants } from 'framer-motion';
import { HumanVerification } from './HumanVerification';
import { GoogleLoginButton } from './GoogleLoginButton';
import { ShieldCheck } from 'lucide-react';

interface AuthCardProps {
  onLoginComplete: () => void;
}

const containerVariants: Variants = {
  hidden: { opacity: 0, y: 30 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.8,
      ease: [0.16, 1, 0.3, 1] as [number, number, number, number], // Custom premium easeOutExpo
      staggerChildren: 0.15,
    },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 15 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: 'easeOut' },
  },
};

export const AuthCard: React.FC<AuthCardProps> = ({ onLoginComplete }) => {
  const [isVerified, setIsVerified] = useState(false);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="w-full max-w-[420px] p-8 sm:p-10 rounded-3xl bg-card border border-border shadow-[0_20px_50px_rgba(27,67,50,0.06)] backdrop-blur-md flex flex-col justify-between min-h-[460px] relative z-10"
    >
      {/* Decorative top ambient light bar inside card */}
      <div className="absolute top-0 inset-x-0 h-[1px] bg-gradient-to-r from-transparent via-primary/20 to-transparent rounded-t-3xl" />

      {/* Header section */}
      <div className="space-y-6">
        <motion.div variants={itemVariants} className="space-y-2">
          <h2 className="text-3xl font-semibold tracking-tight text-foreground font-sans">
            Welcome back
          </h2>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Choose your preferred sign-in method to access agricultural intelligence.
          </p>
        </motion.div>

        {/* Verification Stage */}
        <motion.div variants={itemVariants} className="w-full pt-2">
          <HumanVerification 
            onVerifySuccess={() => setIsVerified(true)} 
          />
        </motion.div>

        {/* OAuth Action Button */}
        <motion.div variants={itemVariants} className="w-full pt-2">
          <GoogleLoginButton
            isVerified={isVerified}
            onLoginStart={() => setIsLoggingIn(true)}
            onLoginComplete={onLoginComplete}
          />
        </motion.div>
      </div>

      {/* Security note / policy footer */}
      <motion.div
        variants={itemVariants}
        className="mt-8 pt-6 border-t border-border flex flex-col gap-4 text-center"
      >
        <div className="flex items-center justify-center gap-2 text-[10px] text-muted-foreground/60">
          <ShieldCheck className="w-3.5 h-3.5 text-primary/70" />
          <span>SSL Secure 256-bit Encrypted Session</span>
        </div>
        <p className="text-[10px] text-muted-foreground/50 leading-normal">
          By continuing, you agree to AgriGPT's{' '}
          <a href="#" className="underline hover:text-foreground transition-colors">
            Terms of Service
          </a>{' '}
          and{' '}
          <a href="#" className="underline hover:text-foreground transition-colors">
            Privacy Policy
          </a>.
        </p>
      </motion.div>
    </motion.div>
  );
};
