import { Stack } from 'expo-router';

export default function AttendanceLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="index" />
      <Stack.Screen
        name="mark"
        options={{ animation: 'slide_from_right' }}
      />
    </Stack>
  );
}
