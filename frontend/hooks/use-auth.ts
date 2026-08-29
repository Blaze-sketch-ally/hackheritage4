"use client";

import { useCallback, useEffect, useState } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/client";
import { signInWithGoogle, signInWithIdentifier } from "@/lib/auth";

interface AuthState {
  user: User | null;
  session: Session | null;
  loading: boolean;
}

/** Current auth session + reusable Supabase Auth actions. */
export function useAuth() {
  const [state, setState] = useState<AuthState>({ user: null, session: null, loading: true });

  useEffect(() => {
    let unsubscribe: (() => void) | undefined;

    async function init() {
      try {
        const supabase = createClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();
        setState({ user: session?.user ?? null, session, loading: false });

        const {
          data: { subscription },
        } = supabase.auth.onAuthStateChange((_event, changedSession) => {
          setState({ user: changedSession?.user ?? null, session: changedSession, loading: false });
        });
        unsubscribe = () => subscription.unsubscribe();
      } catch (err) {
        console.error("Supabase auth unavailable:", err);
        setState({ user: null, session: null, loading: false });
      }
    }

    init();

    return () => unsubscribe?.();
  }, []);

  const signIn = useCallback((identifier: string, password: string) => {
    return signInWithIdentifier(createClient(), identifier, password);
  }, []);

  const signInGoogle = useCallback((redirectTo: string) => {
    return signInWithGoogle(createClient(), redirectTo);
  }, []);

  const signOut = useCallback(async () => {
    await createClient().auth.signOut();
  }, []);

  return {
    user: state.user,
    session: state.session,
    loading: state.loading,
    signIn,
    signInWithGoogle: signInGoogle,
    signOut,
  };
}
