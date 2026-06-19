"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import api from "@/lib/api";
import { Users } from "lucide-react";

export default function MyGroupPage() {
  const [groups, setGroups] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/api/groups/my")
      .then((r) => setGroups(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">My Group</h1>
        <p className="text-sm text-muted-foreground mt-1">
          The team(s) you belong to and your peers.
        </p>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[1, 2].map((i) => <div key={i} className="h-32 animate-pulse rounded-xl bg-muted" />)}
        </div>
      ) : groups.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Users size={36} className="mx-auto text-muted-foreground mb-3" />
            <p className="font-medium">You are not in any group yet.</p>
            <p className="text-sm text-muted-foreground mt-1">
              Contact your administrator to be added to a team.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {groups.map((g) => (
            <Card key={g.id}>
              <CardContent className="p-5">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                    <Users size={18} className="text-primary" />
                  </div>
                  <div>
                    <h2 className="font-semibold">{g.name}</h2>
                    {g.description && (
                      <p className="text-xs text-muted-foreground">{g.description}</p>
                    )}
                  </div>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {g.members?.length ?? 0} members
                  </span>
                </div>

                <div className="space-y-1">
                  {(g.members ?? []).map((m: any) => (
                    <div
                      key={m.user_id}
                      className="flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-muted/50"
                    >
                      <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-xs font-bold uppercase">
                        {m.email?.[0] ?? "?"}
                      </div>
                      <div>
                        <p className="text-sm font-medium">{m.email}</p>
                        <p className="text-xs text-muted-foreground capitalize">{m.role}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
