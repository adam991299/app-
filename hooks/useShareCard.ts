import { useRef, useState } from 'react';
import type { View } from 'react-native';
import { captureShareCard, shareImage } from '@/lib/share';

/** Wires up an off-screen <ShareCard ref={cardRef} .../> to a "Share" button: capture
 * it to a PNG and hand that off to the native share sheet. */
export function useShareCard() {
  const cardRef = useRef<View>(null);
  const [sharing, setSharing] = useState(false);

  const triggerShare = async (dialogTitle?: string) => {
    setSharing(true);
    try {
      const uri = await captureShareCard(cardRef);
      await shareImage(uri, dialogTitle);
    } finally {
      setSharing(false);
    }
  };

  return { cardRef, sharing, triggerShare };
}
