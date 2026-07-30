import { useEffect, useRef, useState, useCallback } from 'react';
import { Platform } from 'react-native';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';
import { useAuth } from './useAuth';
import { registerDeviceToken, unregisterAllDeviceTokens } from '@api/notifications/device-tokens';

// ─── Configure how notifications behave when the app is in the foreground ──
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowList: true,
  }),
});

// ─── Android notification channel ─────────────────────────────────────────
async function setupAndroidChannel() {
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'Default',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#6366F1',
    });
  }
}

// ─── Get Expo push token ───────────────────────────────────────────────────
async function getExpoPushToken(): Promise<string | null> {
  if (!Device.isDevice) {
    console.warn('Push notifications require a physical device');
    return null;
  }

  // Check/request permissions
  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    console.warn('Push notification permission not granted');
    return null;
  }

  // Get the project ID from app config
  const projectId =
    Constants?.expoConfig?.extra?.eas?.projectId ??
    Constants?.easConfig?.projectId;

  if (!projectId) {
    console.warn('No EAS project ID found — push tokens may not work');
  }

  try {
    const tokenData = await Notifications.getExpoPushTokenAsync({
      projectId: projectId || undefined,
    });
    return tokenData.data;
  } catch (err) {
    console.warn('Failed to get Expo push token:', err);
    return null;
  }
}

// ─── Hook ──────────────────────────────────────────────────────────────────
interface UsePushNotificationsResult {
  expoPushToken: string | null;
  notification: Notifications.Notification | undefined;
  lastNotificationResponse: Notifications.NotificationResponse | undefined;
}

export function usePushNotifications(): UsePushNotificationsResult {
  const { isAuthenticated, user } = useAuth();
  const [expoPushToken, setExpoPushToken] = useState<string | null>(null);
  const [notification, setNotification] = useState<Notifications.Notification>();
  const [lastNotificationResponse, setLastNotificationResponse] =
    useState<Notifications.NotificationResponse>();

  const notificationListenerRef = useRef<Notifications.Subscription>();
  const responseListenerRef = useRef<Notifications.Subscription>();

  // Register for push notifications when the user authenticates
  useEffect(() => {
    if (!isAuthenticated || !user) return;

    (async () => {
      await setupAndroidChannel();

      const token = await getExpoPushToken();
      if (!token) return;

      setExpoPushToken(token);

      // Send the token to the backend
      const resp = await registerDeviceToken({
        token,
        platform: Platform.OS as 'android' | 'ios',
      });

      if (!resp.ok) {
        console.warn('Failed to register push token with backend:', resp.error?.message);
      }
    })();
  }, [isAuthenticated, user?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Set up notification listeners
  useEffect(() => {
    // Foreground notification received
    notificationListenerRef.current = Notifications.addNotificationReceivedListener(
      (notif) => {
        setNotification(notif);
      },
    );

    // User tapped on a notification
    responseListenerRef.current = Notifications.addNotificationResponseReceivedListener(
      (response) => {
        setLastNotificationResponse(response);
      },
    );

    return () => {
      if (notificationListenerRef.current) {
        Notifications.removeNotificationSubscription(notificationListenerRef.current);
      }
      if (responseListenerRef.current) {
        Notifications.removeNotificationSubscription(responseListenerRef.current);
      }
    };
  }, []);

  return { expoPushToken, notification, lastNotificationResponse };
}

// ─── Helper: schedule a local notification (for testing) ───────────────────
export async function scheduleLocalNotification(title: string, body: string) {
  await Notifications.scheduleNotificationAsync({
    content: { title, body, sound: true },
    trigger: null, // immediate
  });
}
