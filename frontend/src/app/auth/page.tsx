'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { AuthLayout } from '@/components/auth/AuthLayout';
import { AuthCard } from '@/components/auth/AuthCard';

export default function AuthPage() {
  const router = useRouter();

  useEffect(() => {
    // Enforce captcha clearance and secure regeneration on fresh loads
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('agri_auth_verified');
    }
  }, []);

  const handleLoginComplete = () => {
    // Redirect to main chat interface / dashboard
    router.push('/');
  };

  return (
    <AuthLayout>
      <AuthCard onLoginComplete={handleLoginComplete} />
    </AuthLayout>
  );
}
