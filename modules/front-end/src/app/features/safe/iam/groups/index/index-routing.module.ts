import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import {IndexComponent} from "@features/safe/iam/groups/index/index.component";


const routes: Routes = [
  {
    path: '',
    data: {
      breadcrumb: '权限管理 - 组'
    },
    component: IndexComponent,
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
  providers: [
  ]
})
export class IndexRoutingModule { }