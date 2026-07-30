import { Redirect } from 'expo-router';

export default function Index() {
  // The AuthProvider in _layout.tsx handles the routing logic.
  // This just renders the initial state — the protected route guard
  // in _layout.tsx will redirect to login or tabs.
  return null;
}
