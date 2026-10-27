import { test,expect,boot,topic,studio } from './live';

test('PaperOrchestra cannot invent submission approval in the real workspace',async({page,request},info)=>{
  await boot(page);await topic(page,request,'paper-integrity');await studio(page,'Paper LaTeX');
  await page.getByRole('button',{name:'PaperOrchestra',exact:true}).click();
  const panel=page.locator('#panel');
  await expect(panel.getByText('Author Submission Approval',{exact:true})).toBeVisible();
  await expect(panel.getByRole('button',{name:'Sign-Off',exact:true})).toBeDisabled();
  await expect(panel.getByText('The note above is a local draft; this panel does not support submission approval.',{exact:true})).toBeVisible();
  await expect(panel.getByText('Approved',{exact:true})).toHaveCount(0);
  await info.attach('paper-approval-unavailable.png',{body:await page.screenshot(),contentType:'image/png'});
});
