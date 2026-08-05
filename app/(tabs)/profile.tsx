import { Screen } from '@/components/ui/Screen';
import { LoadingState } from '@/components/ui/StateViews';

// Full implementation lands in the Profile/Stats milestone.
export default function ProfileScreen() {
  return (
    <Screen>
      <LoadingState label="Profile & stats coming right up…" />
    </Screen>
  );
}
