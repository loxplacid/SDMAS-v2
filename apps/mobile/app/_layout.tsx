import React from 'react';
import { Slot, Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { AuthProvider, AuthContext } from '../src/contexts/AuthContext';
import { usePushNotifications } from '../src/hooks/usePushNotifications';
import { colors } from '../src/theme/tokens';

function useProtectedRoute() {
  const segments = useSegments();
  const router = useRouter();
  const auth = React.useContext(AuthContext);

  React.useEffect(() => {
    if (auth?.isLoading) return;

    const inAuthGroup = segments[0] === '(auth)';

    if (!auth?.isAuthenticated && !inAuthGroup) {
      // Redirect to login
      router.replace('/(auth)/login');
    } else if (auth?.isAuthenticated && inAuthGroup) {
      // Redirect to home
      router.replace('/(tabs)');
    }
  }, [auth?.isAuthenticated, auth?.isLoading, segments]);
}

function RootNavigator() {
  const auth = React.useContext(AuthContext);

  useProtectedRoute();

  if (auth?.isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.brand[600]} />
      </View>
    );
  }

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="(auth)" />
      <Stack.Screen name="(tabs)" />
      <Stack.Screen
        name="profile"
        options={{
          presentation: 'modal',
          animation: 'slide_from_bottom',
        }}
      />
    </Stack>
  );
}

function PushNotificationInitializer({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { lastNotificationResponse } = usePushNotifications();

  // Navigate to notifications screen when a push notification is tapped
  React.useEffect(() => {
    if (lastNotificationResponse) {
      router.push('/(tabs)/notifications');
    }
  }, [lastNotificationResponse]);

  return <>{children}</>;
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <AuthProvider>
          <StatusBar style="dark" />
          <PushNotificationInitializer>
            <RootNavigator />
          </PushNotificationInitializer>
        </AuthProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.neutral[50],
  },
});
