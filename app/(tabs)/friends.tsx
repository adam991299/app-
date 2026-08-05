import { Screen } from '@/components/ui/Screen';
import { LoadingState } from '@/components/ui/StateViews';

// Full implementation lands in the Friends & Leaderboard milestone.
export default function FriendsScreen() {
  return (
    <Screen>
      <LoadingState label="Friends & leaderboard coming right up…" />
    </Screen>
  );
}
