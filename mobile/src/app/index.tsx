import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Button, StyleSheet, Text, View } from 'react-native';

import { getHealth, type HealthResponse } from '@/api/client';

type HealthState =
  | { kind: 'loading' }
  | { kind: 'ok'; health: HealthResponse }
  | { kind: 'error'; message: string };

// Temporary home screen: proves the app can reach the backend. Replaced when real screens land.
export default function Index() {
  const [state, setState] = useState<HealthState>({ kind: 'loading' });

  const check = useCallback(async () => {
    setState({ kind: 'loading' });
    try {
      setState({ kind: 'ok', health: await getHealth() });
    } catch (error) {
      setState({ kind: 'error', message: error instanceof Error ? error.message : String(error) });
    }
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Essentas</Text>
      {state.kind === 'loading' && <ActivityIndicator />}
      {state.kind === 'ok' && (
        <Text>
          API connected (v{state.health.version}, {state.health.environment})
        </Text>
      )}
      {state.kind === 'error' && (
        <>
          <Text style={styles.error}>API not reachable</Text>
          <Text style={styles.detail}>{state.message}</Text>
          <Button title="Try again" onPress={check} />
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 16 },
  title: { fontSize: 24, fontWeight: '600' },
  error: { color: '#b00020', fontWeight: '600' },
  detail: { textAlign: 'center' },
});
