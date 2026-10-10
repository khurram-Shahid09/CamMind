import { redirect } from "next/navigation";

export default function Home() {
  redirect("/live"); // proxy.ts sends signed-out visitors to /login first
}
