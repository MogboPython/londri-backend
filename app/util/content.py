otp_content_template = """
     <tr>
      <td align="center" class="es-m-p0r es-m-p0l" style="Margin:0;padding:5px 40px"><p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:21px;letter-spacing:0;font-weight:normal;color:#333333;font-size:14px">You’ve received this message because your email address has been registered with our site. Please use the OTP below to verify your email address and confirm that you are the owner of this account.</p></td>
     </tr>
     <tr>
      <td align="center" style="padding:10px 0 5px;Margin:0"><p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:21px;letter-spacing:0;font-weight:normal;color:#333333;font-size:14px">If you did not register with us, please disregard this email.</p></td>
     </tr>
     <tr>
      <td align="center" style="padding:10px 0;Margin:0"><span class="es-button-border" style="border-style:solid;border-color:#2CB543;background:#00806e;border-width:0px;display:inline-block;border-radius:6px;width:auto"><span class="es-button" style="mso-style-priority:100 !important;text-decoration:none !important;mso-line-height-rule:exactly;color:#FFFFFF;font-size:20px;font-weight:normal;padding:10px 30px;display:inline-block;background:#00806e;border-radius:6px;font-family:arial, 'helvetica neue', helvetica, sans-serif;font-style:normal;line-height:24px;width:auto;text-align:center;letter-spacing:0;mso-padding-alt:0;mso-border-alt:10px solid #00806e;text-transform:none">{otp}</span></span></td>
     </tr>
     <tr>
      <td align="center" class="es-m-p0r es-m-p0l" style="Margin:0;padding:5px 40px"><p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:21px;letter-spacing:0;font-weight:normal;color:#333333;font-size:14px">Once confirmed, this email will be uniquely associated with your account.</p></td>
     </tr>
"""

successful_sub_content_template = """
     <tr>
      <td align="left" class="es-m-p0r es-m-p0l" style="Margin:0;padding:5px 40px"><p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:21px;letter-spacing:0;font-weight:normal;color:#333333;font-size:14px">Hello there,</p></td>
     </tr>
     <tr>
      <td align="left" class="es-m-p0r es-m-p0l" style="Margin:0;padding:5px 40px"><p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:21px;letter-spacing:0;font-weight:normal;color:#333333;font-size:14px">Your {plan_name} subscription is now active! You've been charged {amount} for the {duration} plan.</p></td>
     </tr>
     <tr>
      <td align="left" class="es-m-p0r es-m-p0l" style="Margin:0;padding:5px 40px"><p style="Margin:0;mso-line-height-rule:exactly;font-family:arial, 'helvetica neue', helvetica, sans-serif;line-height:21px;letter-spacing:0;font-weight:normal;color:#333333;font-size:14px">We can't wait for your orders. Thanks for choosing Londri!</p></td>
     </tr>
"""
