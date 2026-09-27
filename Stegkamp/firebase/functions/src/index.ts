import { initializeApp } from "firebase-admin/app";
import { setGlobalOptions } from "firebase-functions/v2";
import { REGION } from "./config.js";

initializeApp();
setGlobalOptions({ region: REGION, maxInstances: 10 });

// Functions are exported here as they are built: competitions (phase 3), invites (phase 4),
// settlements (phase 5) and notifications (phase 6).
export {};
