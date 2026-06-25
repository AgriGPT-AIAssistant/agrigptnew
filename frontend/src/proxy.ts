import { auth } from "@/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const isLoggedIn = !!req.auth;
  const isAuthPage = req.nextUrl.pathname.startsWith('/auth');

  // Protect the root and all other routes
  if (!isLoggedIn && !isAuthPage) {
    return NextResponse.redirect(new URL('/auth', req.nextUrl));
  }
  
  // Prevent authenticated users from seeing the login page
  if (isLoggedIn && isAuthPage) {
    return NextResponse.redirect(new URL('/', req.nextUrl));
  }

  return NextResponse.next();
});

export const config = {
  // Apply middleware to all routes except API endpoints and static Next.js assets
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|.*\\.png$).*)'],
};
