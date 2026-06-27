import NextAuth, { type DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    id_token?: string;
    user: {
      id?: string;
    } & DefaultSession["user"];
  }
}
