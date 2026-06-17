import DashboardLayout from "@/components/layout/dashboard-layout";
import { Card, CardContent } from "@/components/ui/card";

export default function DashboardPage() {
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">
          Dashboard
        </h1>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardContent className="p-6">
              <p className="text-sm text-muted-foreground">
                Total Reports
              </p>

              <h2 className="text-3xl font-bold">
                27
              </h2>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <p className="text-sm text-muted-foreground">
                Pending Reviews
              </p>

              <h2 className="text-3xl font-bold">
                4
              </h2>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <p className="text-sm text-muted-foreground">
                Documents
              </p>

              <h2 className="text-3xl font-bold">
                112
              </h2>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <p className="text-sm text-muted-foreground">
                Tasks
              </p>

              <h2 className="text-3xl font-bold">
                13
              </h2>
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}